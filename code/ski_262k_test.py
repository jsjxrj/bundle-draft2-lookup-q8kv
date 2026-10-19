# -*- coding: utf-8 -*-
"""滑雪游戏提示词 262K 对比测试:速度 + 输出完整性 + 稳定性"""
import json, sys, time, urllib.request

PROMPT = """用单个 HTML 文件，通过 CDN 引入 Three.js，做一个 3D 夜间滑雪游戏。
画面：
- 全屏深色夜空背景，有星星和月亮，页面四周不留白边
- 一条向下无限延伸的雪坡，两侧有路灯照亮雪道，远处有雾气
- 雪道上随机生成松树、石头、旗门，远处有山的轮廓
- 第三人称视角，镜头跟在滑雪者身后略高的位置，转弯时镜头有轻微倾斜
玩法：
- 左右方向键控制转向，上方向键加速，下方向键减速
- 速度随时间逐渐加快，撞到树或石头就摔倒，游戏结束
- 从两根旗门之间穿过加 100 分，漏过旗门扣分
- 左上角显示分数、速度（km/h）和滑行距离，右上角显示最高分
- 游戏结束后显示成绩，按空格重新开始
细节：
- 滑雪者用简单的几何体拼出来（身体、头、两根雪杖、两块滑雪板），转弯时身体会倾斜
- 滑雪板后面留下雪痕，高速时有雪粒飞溅的粒子效果
- 用 Web Audio API 生成风声，速度越快风声越大，不要使用外部音频文件
只输出完整代码，不要解释。"""

def run(url, model, out_path, max_tokens=16384, no_think=True, api_key="", temp=0.0):
    msg = {"role": "user", "content": PROMPT}
    payload = {
        "model": model,
        "messages": [msg],
        "max_tokens": max_tokens,
        "temperature": temp,
        "stream": False,
    }
    if no_think:
        payload["chat_template_kwargs"] = {"enable_thinking": False}
    body = json.dumps(payload).encode("utf-8")
    hdrs = {"Content-Type": "application/json"}
    if api_key:
        hdrs["Authorization"] = "Bearer " + api_key
    req = urllib.request.Request(url + "/v1/chat/completions", data=body,
                                 headers=hdrs)
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=1800) as r:
            data = json.loads(r.read().decode("utf-8"))
    except Exception as e:
        print(f"[FAIL] request error: {e}")
        return
    dt = time.time() - t0
    text = data["choices"][0]["message"]["content"]
    fin = data["choices"][0].get("finish_reason")
    u = data.get("usage", {})
    ct = u.get("completion_tokens", 0)
    pps = u.get("prompt_tokens", 0) / dt if dt else 0
    tps = ct / dt if dt else 0
    ends_ok = text.rstrip().endswith("</html>")
    has_html = "<html" in text or "<!DOCTYPE" in text
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"out={out_path}")
    print(f"prompt_tokens={u.get('prompt_tokens')} completion_tokens={ct} finish_reason={fin}")
    print(f"total_time={dt:.1f}s  gen_speed={tps:.2f} tok/s  (prompt_phase ~{pps:.0f} tok/s mixed)")
    print(f"starts_html={has_html} ends_</html>={ends_ok}")
    # 粗检复读:同一行出现超多次
    lines = text.splitlines()
    from collections import Counter
    c = Counter(l for l in lines if len(l.strip()) > 20)
    if c:
        top, n = c.most_common(1)[0]
        if n > 5:
            print(f"[WARN] 疑似复读: 同一行 x{n}: {top[:60]}...")
        else:
            print("no-loop check: OK")

if __name__ == "__main__":
    url, model, out = sys.argv[1], sys.argv[2], sys.argv[3]
    key = sys.argv[4] if len(sys.argv) > 4 else ""
    temp = float(sys.argv[5]) if len(sys.argv) > 5 else 0.0
    run(url, model, out, api_key=key, temp=temp)

