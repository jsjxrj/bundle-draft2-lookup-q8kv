# -*- coding: utf-8 -*-
"""bundle draft2+lookup+q8KV 草稿档位调优: draft 1/2/3 @ temp 0.7 对比
每个档位: 重启引擎 -> 等就绪 -> 预热 -> 滑雪提示词(固定种子) -> 抓日志接受率 -> 落盘结果
"""
import glob, json, os, re, subprocess, sys, time, urllib.request

BUNDLE = 'E:/Code/AI/bonsai-local/262k-bundle/bundle'
KEY = open(BUNDLE + '/artifacts/api_key.txt').read().strip()
URL = 'http://127.0.0.1:8898'
MODEL = 'bonsai-2-27b'
PORT = 8898
RESULTS = 'E:/Code/AI/NInfer-89/draft-tune-results.jsonl'

PROMPT = open('E:/Code/AI/NInfer-89/ski_prompt.txt', encoding='utf-8').read()

def sh(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, shell=False,
                          encoding='gbk', errors='replace')

def kill_port():
    r = sh(['netstat', '-ano', '-p', 'tcp'])
    pids = set()
    for line in r.stdout.splitlines():
        if f':{PORT} ' in line and 'LISTENING' in line.upper():
            try: pids.add(int(line.split()[-1]))
            except ValueError: pass
    for pid in pids:
        sh(['taskkill', '/F', '/T', '/PID', str(pid)])
    # 兜底: 清掉测试包装 powershell
    ps = subprocess.run(['powershell', '-NoProfile', '-Command',
        "Get-CimInstance Win32_Process -Filter \"Name='powershell.exe'\" | "
        "Where-Object { $_.CommandLine -like '*start-draft-test.ps1*' } | "
        "Select-Object -ExpandProperty ProcessId"], capture_output=True, text=True)
    for line in ps.stdout.splitlines():
        try: sh(['taskkill', '/F', '/PID', str(int(line.strip()))])
        except ValueError: pass
    for _ in range(20):
        if not port_alive(): break
        time.sleep(0.5)

def port_alive():
    r = sh(['netstat', '-ano', '-p', 'tcp'])
    return any(f':{PORT} ' in l and 'LISTENING' in l.upper() for l in r.stdout.splitlines())

def start_server(draft):
    logf = open(f'E:/Code/AI/NInfer-89/draft{draft}-server.log', 'w')  # 每轮截断,便于整文件扫描
    subprocess.Popen(
        ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
         'E:/Code/AI/NInfer-89/start-draft-test.ps1', '-Draft', str(draft)],
        stdout=logf, stderr=logf, cwd=BUNDLE)

def wait_health(timeout=120):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            with urllib.request.urlopen(URL + '/health', timeout=3) as r:
                if r.status == 200: return time.time() - t0
        except Exception: pass
        time.sleep(2)
    return None

def chat(payload):
    body = json.dumps(payload).encode()
    req = urllib.request.Request(URL + '/v1/chat/completions', data=body,
        headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + KEY})
    with urllib.request.urlopen(req, timeout=1800) as r:
        return json.loads(r.read())

def bundle_log_lines_since(draft):
    """扫描本轮引擎日志(已截断重定向文件),聚合 draft acceptance 指标"""
    path = f'E:/Code/AI/NInfer-89/draft{draft}-server.log'
    acc, gen, lens = 0, 0, []
    try:
        for line in open(path, encoding='utf-8', errors='ignore'):
            m = re.search(r'draft acceptance = ([\d.]+) \( *(\d+) accepted / *(\d+) generated\), mean len = *([\d.]+)', line)
            if m:
                acc += int(m.group(2)); gen += int(m.group(3)); lens.append(float(m.group(4)))
    except FileNotFoundError:
        pass
    return acc, gen, lens

def main():
    drafts = [int(a) for a in sys.argv[1:]] or [1, 2, 3]
    out = open(RESULTS, 'a', encoding='utf-8')
    for draft in drafts:
        print(f'===== draft {draft} =====', flush=True)
        kill_port()
        t_kill = time.time()
        start_server(draft)
        dt = wait_health()
        if dt is None:
            print(f'draft {draft}: server failed to start', flush=True)
            out.write(json.dumps({'draft': draft, 'error': 'start failed'}) + '\n'); out.flush()
            continue
        print(f'server up in {dt:.0f}s', flush=True)
        log_ts = time.time()
        # 预热(短请求, 让权重/缓存就位; 不计入指标)
        try:
            chat({'model': MODEL, 'messages': [{'role': 'user', 'content': 'hi'}],
                  'max_tokens': 16, 'temperature': 0.7, 'seed': 42,
                  'chat_template_kwargs': {'enable_thinking': False}})
        except Exception as e:
            print('warmup fail:', e, flush=True)
        # 正式测: 滑雪提示词 temp0.7 seed42
        t0 = time.time()
        try:
            d = chat({'model': MODEL, 'messages': [{'role': 'user', 'content': PROMPT}],
                      'max_tokens': 16384, 'temperature': 0.7, 'seed': 42,
                      'chat_template_kwargs': {'enable_thinking': False}})
        except Exception as e:
            print(f'draft {draft}: request error {e}', flush=True)
            out.write(json.dumps({'draft': draft, 'error': str(e)[:200]}) + '\n'); out.flush()
            continue
        wall = time.time() - t0
        ch = d['choices'][0]
        text = ch['message'].get('content') or ''
        u = d.get('usage', {})
        ct = u.get('completion_tokens', 0)
        acc, gen, lens = bundle_log_lines_since(draft)
        # 服务端 timings 更准
        tim = d.get('timings') or {}
        tps_srv = (tim.get('predicted_n') or 0) / (tim.get('predicted_ms') or 1) * 1000
        rec = {
            'draft': draft, 'wall_s': round(wall, 1),
            'completion_tokens': ct, 'tps_wall': round(ct / wall, 2),
            'tps_server': round(tps_srv, 2),
            'finish': ch.get('finish_reason'),
            'complete_html': '</html>' in text,
            'accept_acc': acc, 'accept_gen': gen,
            'accept_rate': round(acc / gen, 4) if gen else None,
            'mean_accepted_len': round(sum(lens) / len(lens), 3) if lens else None,
        }
        print(json.dumps(rec, ensure_ascii=False), flush=True)
        out.write(json.dumps(rec, ensure_ascii=False) + '\n'); out.flush()
        open(f'E:/Code/AI/NInfer-89/ski-draft{draft}.html', 'w', encoding='utf-8').write(text)
    out.close()
    print('DONE', flush=True)

if __name__ == '__main__':
    main()
