#!/usr/bin/env python3
"""ToAPIs image client. One submit per job directory; no POST retries."""
import argparse, fcntl, hashlib, io, json, mimetypes, os, re, time
from pathlib import Path
from urllib.parse import quote, urlparse
import requests
from PIL import Image
MODEL = 'gemini-3-pro-image-preview'
ALLOWED_FALLBACK = frozenset({'technical'})

class ClientError(Exception): pass

def classify(error):
    text = json.dumps(error, ensure_ascii=False).lower()
    if any(s in text for s in ('moderation', 'safety', 'content_policy', 'content_filter', 'sexual', '审核', '安全系统', 'policy_violation')):
        return 'safety'
    if any(s in text for s in ('authentication', 'invalid_api_key', 'insufficient', 'billing', '余额', 'invalid_parameter')):
        return 'configuration'
    if isinstance(error, dict) and error.get('status_code') in (400,401,402,403,422):
        return 'configuration'
    if any(s in text for s in ('timeout', 'timed out', 'connectionerror', 'connection refused', 'service unavailable', 'bad gateway', '超时')):
        return 'technical'
    if isinstance(error, dict) and error.get('status_code') in (502,503,504):
        return 'technical'
    return 'unknown'

def require_fallback(failure):
    if failure is None:
        return 'direct_authorized'
    category = classify(failure)
    if category not in ALLOWED_FALLBACK:
        raise ClientError('禁止备用提交：'+category)
    return category

def atomic(path, value):
    from pipeline_common import save_json
    save_json(path, value)

def credential():
    key = os.environ.get('TOAPIS_API_KEY', '').strip()
    if not key:
        p = Path.home()/'.config/toapis/api-key'
        if p.exists():
            if p.stat().st_mode & 0o077: raise ClientError('凭据文件权限须为600')
            key = p.read_text().strip()
    if not key: raise ClientError('未配置TOAPIS_API_KEY或~/.config/toapis/api-key')
    return key

class Client:
    def __init__(self, key, base='https://toapis.cn'):
        if base not in ('https://toapis.cn','https://toapis.com'):raise ClientError('不支持的API地址')
        self.base=base;self.session=requests.Session()
        self.session.headers['Authorization']='Bearer '+key
    def call(self, method, path, **kwargs):
        try:r=self.session.request(method,self.base+path,timeout=(15,60),allow_redirects=False,**kwargs)
        except requests.RequestException:raise ClientError('网络请求失败或超时；提交结果可能未知，请勿重复提交') from None
        try:data=r.json()
        except ValueError:raise ClientError('服务返回非JSON响应') from None
        # A failed async task is a valid status response, not a failed GET.
        # Let poll persist its terminal state so it cannot look pending forever.
        task_failure = method == 'GET' and path.startswith('/v1/images/generations/') and data.get('status') == 'failed'
        if not r.ok or (data.get('error') and not task_failure) or data.get('success') is False:
            category=classify({'status_code':r.status_code,'error':data.get('error'), 'message':data.get('message')})
            raise ClientError(f'API失败：HTTP {r.status_code}，类别 {category}')
        return data
    def upload(self,path):
        with path.open('rb') as f:
            result=self.call('POST','/v1/uploads/images',files={'file':(path.name,f,mimetypes.guess_type(path.name)[0])})
        url=result.get('data',{}).get('url')
        if not url or urlparse(url).scheme!='https':raise ClientError('上传未返回HTTPS图片URL')
        return url

def submit(client, directory, prompt, refs, size='1:1', resolution='1K', failure=None):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    with (directory/'submit.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        jp=directory/'job.json'
        if jp.exists():raise ClientError('此目录已有提交记录；请使用poll续查，禁止重复提交')
        category=require_fallback(failure)
        if failure is not None and isinstance(failure,dict) and (failure.get('task_id') or failure.get('prompt_id')):
            raise ClientError('原服务已有任务ID，先查明终态，不能自动提交备用')
        if not prompt.strip() or len(prompt)>1000 or len(refs)>6:raise ClientError('文案须为1–1000字符，参考最多6张')
        reference_info=[]
        for ref in refs:
            p=Path(ref).resolve()
            if p.stat().st_size>10*1024*1024:raise ClientError('参考图片超过10MB')
            with Image.open(p) as im:
                if im.format not in ('PNG','JPEG','WEBP'):raise ClientError('参考格式须为PNG/JPEG/WebP')
                im.verify()
            reference_info.append({'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
        job={'provider':'ToAPIs','model':MODEL,'base':client.base,'status':'preparing','fallback_category':category,'refs':reference_info,'attempt':1,'prompt_sha256':hashlib.sha256(prompt.encode()).hexdigest()}
        atomic(jp,job);(directory/'prompt.txt').write_text(prompt)
        try:
            urls=[client.upload(Path(x['path'])) for x in reference_info]
            payload={'model':MODEL,'prompt':prompt,'size':size,'n':1,'metadata':{'resolution':resolution}}
            if urls:payload['image_urls']=urls
            job['status']='submitting_unknown';atomic(jp,job)
            data=client.call('POST','/v1/images/generations',json=payload)
            ident=data.get('id')
            if not ident:raise ClientError('提交未返回任务ID；结果未知，禁止自动重提')
            job.update(task_id=ident,status=data.get('status','queued'),size=size,resolution=resolution)
            atomic(jp,job)
        except ClientError as e:
            job['last_error']=str(e);atomic(jp,job);raise
        return job

def poll(client,directory):
    directory=Path(directory);jp=directory/'job.json';job=json.loads(jp.read_text())
    if not job.get('task_id'):raise ClientError('没有任务ID，请先核对未知提交，不能重提')
    data=client.call('GET','/v1/images/generations/'+quote(job['task_id'],safe=''))
    status=data.get('status');job['status']=status;job['progress']=data.get('progress')
    if status=='failed':
        job['failure_category']=classify(data.get('error',{}));atomic(jp,job)
        raise ClientError('生成失败：'+job['failure_category'])
    if status=='completed':
        results=data.get('result',{}).get('data',[])
        if not results and data.get('url'):results=[{'url':data['url']}]
        if not results:raise ClientError('完成响应缺少图片，不能标为成功')
        outputs=[]
        for i,item in enumerate(results):
            url=item.get('url','')
            if urlparse(url).scheme!='https':raise ClientError('生成结果不是HTTPS URL')
            # Download without API Authorization; do not send credentials to image hosts.
            try:
                with requests.get(url,timeout=(15,60),stream=True) as r:
                    r.raise_for_status();chunks=[];length=0
                    for chunk in r.iter_content(65536):
                        length+=len(chunk)
                        if length>50*1024*1024:raise ClientError('生成图片超过50MB')
                        chunks.append(chunk)
                raw=b''.join(chunks)
                with Image.open(io.BytesIO(raw)) as im:im.load();w,h=im.size;fmt=im.format
            except (requests.RequestException,OSError,ValueError):raise ClientError('图片下载或解码失败，可使用poll重试下载') from None
            ext={'PNG':'.png','JPEG':'.jpg','WEBP':'.webp'}.get(fmt)
            if not ext:raise ClientError('返回格式不支持')
            dest=directory/f'image_{i+1}{ext}';tmp=dest.with_suffix('.part');tmp.write_bytes(raw);tmp.replace(dest)
            outputs.append({'path':str(dest.resolve()),'width':w,'height':h,'sha256':hashlib.sha256(raw).hexdigest()})
        job.update(outputs=outputs,technical_status='passed',visual_status='pending_review');atomic(jp,job)
    else:atomic(jp,job)
    return job

def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['submit','poll']);p.add_argument('--job-dir',type=Path,required=True);p.add_argument('--prompt-file',type=Path);p.add_argument('--ref',type=Path,action='append',default=[]);p.add_argument('--size',choices=['1:1','9:16','16:9','3:2','2:3','4:3','3:4'],default='1:1');p.add_argument('--resolution',choices=['1K','2K','4K'],default='1K');p.add_argument('--failure-json',type=Path);p.add_argument('--direct',action='store_true',help='Independent explicitly requested Gemini job, not a fallback after a refusal');a=p.parse_args()
    if a.action=='submit':
        if not a.prompt_file or bool(a.failure_json)==a.direct:p.error('submit需prompt-file，且选择failure-json或direct之一')
        failure=json.loads(a.failure_json.read_text()) if a.failure_json else None
        # Gate before credentials or network.
        require_fallback(failure)
        c=Client(credential());job=submit(c,a.job_dir,a.prompt_file.read_text(),a.ref,a.size,a.resolution,failure)
    else:
        existing=json.loads((a.job_dir/'job.json').read_text());c=Client(credential(),existing.get('base','https://toapis.cn'));job=poll(c,a.job_dir)
    print(json.dumps({k:job.get(k) for k in ('task_id','status','progress','outputs')},ensure_ascii=False))
if __name__=='__main__':
    try:main()
    except (ClientError,OSError,ValueError,BlockingIOError) as e:
        print('ERROR:',str(e) if isinstance(e,ClientError) else '配置/文件错误或任务正在提交');raise SystemExit(1)
