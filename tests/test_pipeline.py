import contextlib
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import build_workflows as build
import pipeline_common as common
import submit_jobs as submit
import monitor_jobs as monitor
import runtime_check
import check_production_review as review_check

ROOT = Path(__file__).resolve().parents[1]


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name).resolve()
        (self.project / 'jobs').mkdir()
        (self.project / 'workflows').mkdir()
        self.segment = {'id': 1, 'seed': 42}
        self.workflow = {'1': {'class_type': 'Example', 'inputs': {}}}
        common.save_json(self.project / 'workflows/seg_01_api.json', self.workflow)
        common.save_json(self.project / 'jobs/params.json', {'segments': [self.segment]})

    def job(self, status='submitted', **extra):
        result = {'segment': 1, 'base_url': 'http://example.invalid', 'client_id': 'example-request',
                  'prompt_id': 'example-prompt', 'attempt': 1, 'status': status,
                  'source_workflow_sha256': common.digest(self.workflow)}
        result.update(extra)
        common.save_json(submit.job_path(self.project, 1), result)
        return result

    def template(self, name):
        return common.load_json(ROOT / 'assets/templates' / (name + '.json'))

    def image(self, name):
        path = self.project / name
        path.write_bytes(b'local fixture')
        return str(path)

    def test_i2v_rejects_unsupported_tail(self):
        graph = self.template('i2v')
        with self.assertRaisesRegex(RuntimeError, 'last_frame'):
            build.apply_image_conditions(graph, {'first_frame': self.image('first.png'), 'last_frame': self.image('last.png')}, self.project)

    def test_i2v_preserves_first_frame_binding(self):
        graph = self.template('i2v')
        first = self.image('first.png')
        build.apply_image_conditions(graph, {'first_frame': first}, self.project)
        self.assertEqual(graph['1']['inputs']['image'], first)

    def test_custom_tail_is_bound_by_semantic_input_not_node_order(self):
        first = self.image('first.png')
        last = self.image('last.png')
        graph = {'tail': {'class_type': 'LoadImage', 'inputs': {'image': ''}},
                 'main': {'class_type': 'MiniMaxH3ImageToVideo', 'inputs': {'first_frame': ['head', 0], 'last_frame': ['tail', 0]}},
                 'head': {'class_type': 'LoadImage', 'inputs': {'image': ''}}}
        build.apply_image_conditions(graph, {'first_frame': first, 'last_frame': last}, self.project)
        self.assertEqual(graph['head']['inputs']['image'], first)
        self.assertEqual(graph['tail']['inputs']['image'], last)

    def test_ref_count_mismatch_cannot_drop_or_duplicate_images(self):
        ref = self.image('ref.png')
        for refs in ([ref], [ref, ref, ref]):
            with self.assertRaisesRegex(RuntimeError, 'Reference count'):
                build.apply_image_conditions(self.template('ref2va'), {'refs': refs}, self.project)

    def test_shared_loader_rejected(self):
        graph = {'a': {'class_type': 'LoadImage', 'inputs': {'image': ''}},
                 'b': {'class_type': 'MiniMaxH3ImageToVideo', 'inputs': {'first_frame': ['a', 0], 'last_frame': ['a', 0]}}}
        ref = self.image('ref.png')
        with self.assertRaisesRegex(RuntimeError, 'share'):
            build.apply_image_conditions(graph, {'first_frame': ref, 'last_frame': ref}, self.project)

    def test_post_timeout_is_not_replayed(self):
        with patch.object(common.urllib.request, 'urlopen', side_effect=TimeoutError) as network, patch.object(common.time, 'sleep'):
            with self.assertRaises(RuntimeError):
                common.http_json('http://example.invalid', '/prompt', method='POST', payload={})
            self.assertEqual(network.call_count, 1)

    def test_unknown_submission_is_persisted_before_request(self):
        def fail(*args, **kwargs):
            saved = common.load_json(submit.job_path(self.project, 1))
            self.assertEqual(saved['status'], 'submitting_unknown')
            self.assertTrue(Path(saved['request_snapshot']).is_file())
            raise TimeoutError()
        with patch.object(submit, 'http_json', side_effect=fail) as network:
            with self.assertRaises(RuntimeError):
                submit.submit_segment(self.project, self.segment, self.workflow, 'http://example.invalid')
            self.assertEqual(network.call_count, 1)
        self.assertEqual(common.load_json(submit.job_path(self.project, 1))['status'], 'submitting_unknown')

    def test_dry_run_never_touches_network(self):
        argv = ['submit_jobs.py', '--project', str(self.project), '--dry-run']
        with patch('sys.argv', argv), patch.object(submit, 'upload_workflow_assets') as upload, patch.object(common.urllib.request, 'urlopen', side_effect=AssertionError('network')) as network, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(submit.main(), 0)
            upload.assert_not_called()
            network.assert_not_called()

    def test_changed_reference_bytes_cannot_reuse_submission(self):
        image = self.image('ref.png')
        graph = {'1': {'class_type': 'LoadImage', 'inputs': {'image': image}}}
        snapshot = self.project / 'snapshot.json'
        common.save_json(snapshot, {'refs': [{'node': '1', 'path': image, 'sha256': common.file_sha(image)}]})
        job = self.job(source_workflow_sha256=common.digest(graph), request_snapshot=str(snapshot))
        Path(image).write_bytes(b'new version')
        with self.assertRaisesRegex(RuntimeError, 'Reference content changed'):
            submit.ensure_original_inputs(self.project, graph, job)

    def test_unknown_job_cannot_be_resubmitted(self):
        self.job('submitting_unknown')
        argv = ['submit_jobs.py', '--project', str(self.project), '--base-url', 'http://example.invalid']
        with patch('sys.argv', argv), patch.object(submit, 'submit_segment') as post:
            with self.assertRaises(RuntimeError):
                submit.main()
            post.assert_not_called()

    def test_recovery_matches_server_history(self):
        job = self.job('submitting_unknown')
        history = {'recovered': {'prompt': [0, 'recovered', {}, {'h3_request_id': 'example-request'}]}}
        with patch.object(submit, 'http_json', side_effect=[{}, history]):
            found = submit.recover_unknown(self.project, job)
        self.assertEqual(found['prompt_id'], 'recovered')
        self.assertEqual(found['status'], 'submitted')

    def test_ambiguous_recovery_remains_unknown(self):
        job = self.job('submitting_unknown')
        queue = {'queue_pending': [[0, 'one', {}, {'client_id': 'example-request'}], [1, 'two', {}, {'client_id': 'example-request'}]]}
        with patch.object(submit, 'http_json', side_effect=[queue, {}]):
            with self.assertRaises(RuntimeError):
                submit.recover_unknown(self.project, job)
        self.assertEqual(common.load_json(submit.job_path(self.project, 1))['status'], 'submitting_unknown')

    def test_download_failure_never_regenerates(self):
        job = self.job('generated', media=[{'filename': 'clip.mp4'}])
        with patch.object(monitor, 'download_media', side_effect=OSError), patch.object(monitor, 'submit_segment') as post:
            self.assertEqual(monitor.poll_job(self.project, self.segment, job, 10, 0), 'attention')
            self.assertEqual(job['status'], 'download_failed')
            monitor.poll_job(self.project, self.segment, job, 10, 0)
            post.assert_not_called()
        self.assertEqual(job['prompt_id'], 'example-prompt')
        self.assertEqual(job['attempt'], 1)

    def test_zero_generation_retries_is_respected(self):
        job = self.job('generation_failed')
        with patch.object(monitor, 'submit_segment') as post:
            self.assertEqual(monitor.poll_job(self.project, self.segment, job, 0, 3), 'attention')
            post.assert_not_called()

    def test_attempt_increases_only_on_submit(self):
        job = self.job()
        with patch.object(monitor, 'http_json', return_value={'example-prompt': {'status': {'status_str': 'error'}}}):
            monitor.poll_job(self.project, self.segment, job, 1, 3)
        self.assertEqual(job['attempt'], 1)
        with patch.object(monitor, 'submit_segment') as post:
            monitor.poll_job(self.project, self.segment, job, 1, 3)
            self.assertEqual(post.call_args.args[4], 2)

    def test_multiple_outputs_preserved(self):
        job = self.job('generated', media=[{'filename': 'one.mp4'}, {'filename': 'two.mp4'}])
        def download(base, item, dest):
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(item['filename'].encode())
        with patch.object(monitor, 'download_media', side_effect=download):
            self.assertEqual(monitor.poll_job(self.project, self.segment, job, 0, 0), 'done')
        self.assertEqual(len(job['outputs']), 2)
        self.assertEqual(job['production_status'], 'needs_review')
        self.assertNotEqual(job['outputs'][0]['sha256'], job['outputs'][1]['sha256'])

    def test_missing_history_and_queue_requires_reconciliation(self):
        job = self.job()
        with patch.object(monitor, 'http_json', return_value={}):
            for _ in range(3):
                state = monitor.poll_job(self.project, self.segment, job, 0, 0)
        self.assertEqual(state, 'attention')
        self.assertEqual(job['status'], 'needs_reconciliation')

    def test_mode_map_applies_after_inference(self):
        graph = self.template('t2v')
        common.save_json(self.project / 'custom.json', graph)
        segment = {'id': 1}
        mode, result = build.resolve_mode_and_template(segment, ROOT / 'assets/templates', self.project, {'workflow_map': {'t2v': 'custom.json'}})
        self.assertEqual(mode, 't2v')
        self.assertEqual(result, graph)

    def test_example_builds_without_private_assets(self):
        import shutil
        project = self.project / 'example'
        shutil.copytree(ROOT / 'examples/minimal', project)
        result = build.build(project, ROOT / 'assets/templates', None)
        self.assertEqual(len(result['segments']), 1)
        self.assertTrue((project / 'workflows/seg_01_api.json').is_file())

    def test_rebuild_after_submission_rejected(self):
        import shutil
        project = self.project / 'example'
        shutil.copytree(ROOT / 'examples/minimal', project)
        common.save_json(project / 'jobs/seg_01_job.json', {'status': 'submitted'})
        with self.assertRaisesRegex(RuntimeError, 'submitted jobs'):
            build.build(project, ROOT / 'assets/templates', None)

    def test_runtime_offline_does_not_probe_or_require_history(self):
        with patch.object(runtime_check, 'http_json') as net:
            result = runtime_check.check(self.project, offline=True)
        net.assert_not_called()
        self.assertNotIn('paths', result)
        self.assertFalse(result['network_checked'])

    def test_review_cannot_reuse_stale_artifact_sha(self):
        clip = self.project / 'clip.mp4'
        clip.write_bytes(b'current clip')
        old_sha = '0' * 64
        manifest = [{'request_id': 'demo', 'revision': 'v1', 'sequence': 1, 'file': str(clip), 'sha256': old_sha, 'prompt_id': 'task'}]
        review = {'request_id': 'demo', 'revision': 'v1', 'unresolved_feedback': [], 'clips': manifest}
        errors = review_check.check(review, manifest, self.project, self.project)
        self.assertIn('delivery: SHA mismatch', errors)


if __name__ == '__main__':
    unittest.main()
