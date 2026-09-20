import io,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
import gemini_image as g
class Fake:
    base='https://toapis.cn'
    def __init__(self):self.calls=[]
    def upload(self,p):self.calls.append('upload');return 'https://files.toapis.com/reference.png'
    def call(self,method,path,**kwargs):
        self.calls.append((method,path,kwargs))
        if method=='POST':return {'id':'test_1','status':'queued'}
        return {'status':'completed','result':{'data':[{'url':'https://files.toapis.com/result.png'}]}}
class Response:
    def __enter__(self):return self
    def __exit__(self,*a):pass
    def raise_for_status(self):pass
    def iter_content(self,n):
        b=io.BytesIO();Image.new('RGB',(64,64),'blue').save(b,format='PNG');yield b.getvalue()
class Tests(unittest.TestCase):
    def test_http200_failed_task_is_persisted(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'job.json';p.write_text(json.dumps({'task_id':'failed_1','model':g.MODEL}))
            c=g.Client('test-only')
            class FailedResponse:
                ok=True
                status_code=200
                def json(self):return {'status':'failed','error':{'code':'generation_failed'}}
            with patch.object(c.session,'request',return_value=FailedResponse()):
                with self.assertRaises(g.ClientError):g.poll(c,d)
            self.assertEqual(json.loads(p.read_text())['status'],'failed')
    def test_pro_payload_and_limits(self):
        with tempfile.TemporaryDirectory() as d:
            c=Fake();g.submit(c,d,'A blue cup',[])
            self.assertEqual(c.calls[-1][2]['json']['model'],'gemini-3-pro-image-preview')
        for prompt,refs in [('x'*1001,[]),('normal',[Path('unused.png')]*7)]:
            with tempfile.TemporaryDirectory() as d:
                c=Fake()
                with self.assertRaises(g.ClientError):g.submit(c,d,prompt,refs)
                self.assertEqual(c.calls,[])
    def test_resume_preserves_legacy_model(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'job.json';p.write_text(json.dumps({'task_id':'legacy_123','model':'gemini-3.1-flash-image-preview'}))
            c=Fake()
            with patch.object(g.requests,'get',return_value=Response()):result=g.poll(c,d)
            self.assertEqual(result['model'],'gemini-3.1-flash-image-preview')
            self.assertEqual(c.calls[0][:2],('GET','/v1/images/generations/legacy_123'))
    def test_gate(self):
        for error in [{'error':'unclassified'},{'status_code':401}]:
            with tempfile.TemporaryDirectory() as d:
                c=Fake()
                with self.assertRaises(g.ClientError):g.submit(c,d,'normal',[],failure=error)
                self.assertEqual(c.calls,[])
    def test_safety_fallback_is_blocked(self):
        for error in [{'status_code':503,'error':'moderation_blocked'},{'category':'sexual'},{'error':'safety_violations'}]:
            with tempfile.TemporaryDirectory() as d:
                c=Fake()
                with self.assertRaises(g.ClientError):g.submit(c,d,'normal',[],failure=error)
                self.assertEqual(c.calls,[])
    def test_known_original_task(self):
        with tempfile.TemporaryDirectory() as d:
            c=Fake()
            with self.assertRaises(g.ClientError):g.submit(c,d,'normal',[],failure={'error':'timeout','task_id':'existing'})
            self.assertEqual(c.calls,[])
    def test_upload_resume(self):
        with tempfile.TemporaryDirectory() as d:
            r=Path(d)/'ref.png';Image.new('RGB',(32,32),'red').save(r);job=Path(d)/'job';c=Fake()
            g.submit(c,job,'A blue cup',[r],failure={'error':'service unavailable'})
            self.assertIn('image_urls',c.calls[-1][2]['json'])
            with self.assertRaises(g.ClientError):g.submit(c,job,'A blue cup',[r])
            with patch.object(g.requests,'get',return_value=Response()) as download:
                result=g.poll(c,job)
                self.assertNotIn('headers',download.call_args.kwargs)
            self.assertEqual(result['outputs'][0]['width'],64)
            self.assertEqual(result['visual_status'],'pending_review')
    def test_unknown_submit_no_duplicate(self):
        with tempfile.TemporaryDirectory() as d:
            c=Fake()
            def fail(*a,**kw):raise g.ClientError('network timeout')
            c.call=fail
            with self.assertRaises(g.ClientError):g.submit(c,d,'A blue cup',[])
            self.assertEqual(json.loads((Path(d)/'job.json').read_text())['status'],'submitting_unknown')
            with self.assertRaises(g.ClientError):g.submit(c,d,'A blue cup',[])
    def test_failed_output(self):
        with tempfile.TemporaryDirectory() as d:
            c=Fake();g.submit(c,d,'A blue cup',[])
            c.call=lambda *a,**k:{'status':'failed','error':{'code':'safety_rejected'}}
            with self.assertRaises(g.ClientError):g.poll(c,d)
            self.assertEqual(json.loads((Path(d)/'job.json').read_text())['failure_category'],'safety')
if __name__=='__main__':unittest.main()
