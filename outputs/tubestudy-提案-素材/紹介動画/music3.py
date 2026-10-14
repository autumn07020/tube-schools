# -*- coding: utf-8 -*-
"""紹介動画（52秒・第3版）の音。最初からアップビート → 途中で穏やかに → 最後に持ち上げて、静かになってから印の「ぽこん」。

  0.50  ぽこん／0.53 輪／1.22 銘（印）
  2.15  刻みが入り始め（ハイハット・軽いキック）→ 3.4 でビートが落ちる（4つ打ち）
  3.4   S2 …… 8.4 S3 …… 13.4 S4 …… 18.4 S5 …… 23.4 S6 …… 28.4 S7（頂点）
 33.4   S8 プライバシー：打楽器を抜いて、パッドと鐘だけ（穏やか）
 38.4   S9 もう一度全部。最後の2小節は F → G（IV–V）で持ち上げ、43.4 の C で解決
 43.4   S10 大きく温かい和音（合唱ふうのパッド＋高い鐘）→ 46.6 で無音
 46.9   印。47.01 ぽこん／47.03 輪／47.72 銘
96 BPM（1小節 2.5秒）。場面は2小節ごと。
"""
import numpy as np, wave, sys

SR = 44100
DUR = 62.0
N = int(SR * DUR)
L = np.zeros(N); R = np.zeros(N)
t_all = np.arange(N) / SR

def put(sig, t0, pan=0.0, gain=1.0):
    i0 = int(t0 * SR)
    if i0 >= N or i0 < 0: return
    seg = sig[:N - i0] * gain
    gl = np.sqrt(0.5 * (1 - pan)); gr = np.sqrt(0.5 * (1 + pan))
    L[i0:i0 + len(seg)] += seg * gl
    R[i0:i0 + len(seg)] += seg * gr

def env_adsr(n, a, d, s, r, sr=SR):
    a_n, d_n, r_n = int(a * sr), int(d * sr), int(r * sr)
    e = np.ones(n)
    a_n = min(a_n, n)
    if a_n: e[:a_n] = np.linspace(0, 1, a_n, endpoint=False)
    if d_n and a_n + d_n <= n: e[a_n:a_n + d_n] = np.linspace(1, s, d_n); e[a_n + d_n:] = s
    elif a_n < n: e[a_n:] = s
    r_n = min(r_n, n)
    if r_n: e[-r_n:] *= np.linspace(1, 0, r_n)
    return e

def midi(m): return 440.0 * 2 ** ((m - 69) / 12.0)

# ---- 音色 ----
def pluck(f, dur=0.5, vel=1.0):
    n = int(dur * SR); t = np.arange(n) / SR
    w = (np.sin(2 * np.pi * f * t) + 0.35 * np.sin(2 * np.pi * 2 * f * t + 0.3) + 0.12 * np.sin(2 * np.pi * 3 * f * t)
         + 0.08 * np.sin(2 * np.pi * f * 1.004 * t))
    e = np.exp(-t / 0.2) * (1 - np.exp(-t / 0.003))
    return w * e * 0.22 * vel

def bell(f, dur=1.2, vel=1.0):
    n = int(dur * SR); t = np.arange(n) / SR
    w = np.sin(2 * np.pi * f * t) + 0.5 * np.sin(2 * np.pi * 2.0 * f * t) * np.exp(-t / 0.3) + 0.25 * np.sin(2 * np.pi * 3.01 * f * t) * np.exp(-t / 0.15)
    e = np.exp(-t / 0.45) * (1 - np.exp(-t / 0.003))
    return w * e * 0.18 * vel

def pad(freqs, dur, vel=1.0, attack=0.9, pump=None):
    """pump=(beat秒) を渡すと、拍ごとに少し沈む（サイドチェーンふう）"""
    n = int(dur * SR); t = np.arange(n) / SR
    w = np.zeros(n)
    for f in freqs:
        for det in (0.0, 0.0025, -0.0025):
            w += np.sin(2 * np.pi * f * (1 + det) * t + np.random.rand() * 6.28)
        w += 0.35 * np.sin(2 * np.pi * 2 * f * t) + 0.12 * np.sin(2 * np.pi * 3 * f * t)
    w /= (len(freqs) * 3.5)
    w *= 1 + 0.08 * np.sin(2 * np.pi * 0.35 * t)
    e = env_adsr(n, attack, 0.3, 0.85, min(0.6, dur / 3))
    if pump:
        ph = (t % pump) / pump
        e = e * (0.55 + 0.45 * np.clip(ph * 4, 0, 1))          # 拍頭で沈み、すぐ戻る
    return w * e * 0.20 * vel

def choir(freqs, dur, vel=1.0, attack=0.8):
    """合唱ふう：少しずつずれた鋸波を重ね、ゆっくり開く（最後の和音に）"""
    n = int(dur * SR); t = np.arange(n) / SR
    w = np.zeros(n)
    for f in freqs:
        for det in (-0.006, -0.002, 0.002, 0.006):
            ph = (t * f * (1 + det)) % 1.0
            saw = 2 * ph - 1
            w += saw - 0.5 * (2 * ((t * f * (1 + det) * 2) % 1.0) - 1)
    w /= (len(freqs) * 4 * 1.5)
    # 上を少し丸める（移動平均）
    w = np.convolve(w, np.ones(24) / 24, mode="same")
    e = env_adsr(n, attack, 0.5, 0.9, min(1.2, dur / 2.5))
    return w * e * 0.16 * vel

def bass(f, dur=0.6, vel=1.0):
    n = int(dur * SR); t = np.arange(n) / SR
    w = np.sin(2 * np.pi * f * t) + 0.3 * np.sin(2 * np.pi * 2 * f * t) * np.exp(-t / 0.25) + 0.08 * np.sign(np.sin(2 * np.pi * f * t)) * np.exp(-t / 0.08)
    e = env_adsr(n, 0.006, 0.15, 0.7, 0.12)
    return w * e * 0.30 * vel

def kick(vel=1.0):
    n = int(0.3 * SR); t = np.arange(n) / SR
    f = 44 + 95 * np.exp(-t / 0.042)
    ph = 2 * np.pi * np.cumsum(f) / SR
    click = np.random.randn(n) * np.exp(-t / 0.0018) * 0.3
    return (np.sin(ph) * np.exp(-t / 0.13) + click) * 0.66 * vel

def clap(vel=1.0):
    n = int(0.12 * SR)
    out = np.zeros(n)
    for k, d in enumerate((0.0, 0.011, 0.022)):
        x = np.random.randn(n)
        x = np.convolve(x, np.ones(5) / 5, mode="same") - np.convolve(x, np.ones(40) / 40, mode="same")
        e = np.exp(-np.arange(n) / SR / (0.03 + 0.012 * k))
        i0 = int(d * SR)
        out[i0:] += (x * e)[:n - i0]
    return out * 0.17 * vel

def hat(vel=1.0, open_=False):
    n = int((0.11 if open_ else 0.035) * SR)
    x = np.random.randn(n)
    x = x - np.concatenate([[0], x[:-1]]); x = x - np.concatenate([[0], x[:-1]])
    e = np.exp(-np.arange(n) / SR / (0.06 if open_ else 0.012))
    return x * e * 0.05 * vel

def shaker(vel=1.0):
    n = int(0.07 * SR)
    x = np.random.randn(n); x = x - np.concatenate([[0], x[:-1]])
    e = np.exp(-np.arange(n) / SR / 0.018)
    return x * e * 0.04 * vel

def rim(vel=1.0):
    n = int(0.03 * SR)
    x = np.random.randn(n)
    x = np.convolve(x, np.ones(3) / 3, mode="same") - np.convolve(x, np.ones(12) / 12, mode="same")
    e = np.exp(-np.arange(n) / SR / 0.007)
    return x * e * 0.12 * vel

def riser(dur=1.5, vel=1.0):
    n = int(dur * SR); t = np.arange(n) / SR
    noise = np.random.randn(n); noise = noise - np.concatenate([[0], noise[:-1]])
    return noise * (t / dur) ** 2.2 * 0.06 * vel

# ---- 効果音（印） ----
def pokon(vel=1.0):
    n = int(0.36 * SR); t = np.arange(n) / SR
    f1 = 330 + (760 - 330) * np.clip(t / 0.055, 0, 1)
    ph1 = 2 * np.pi * np.cumsum(f1) / SR
    po = np.sin(ph1) * np.exp(-t / 0.05) * (1 - np.exp(-t / 0.002))
    t2 = np.clip(t - 0.05, 0, None)
    f2 = 1046.5 * (1 - 0.06 * np.clip(t2 / 0.12, 0, 1))
    ph2 = 2 * np.pi * np.cumsum(f2) / SR
    kon = (np.sin(ph2) + 0.4 * np.sin(2 * ph2) * np.exp(-t2 / 0.05)) * np.exp(-t2 / 0.11) * (t >= 0.05) * (1 - np.exp(-t2 / 0.002))
    return (po * 0.9 + kon * 0.7) * 0.55 * vel

def whirr(dur=0.95, vel=1.0):
    n = int(dur * SR); t = np.arange(n) / SR
    f = 520 * (1.0 + 1.9 * (t / dur) ** 0.8)
    ph = 2 * np.pi * np.cumsum(f) / SR
    trem = 0.55 + 0.45 * np.sin(2 * np.pi * (14 + 10 * t / dur) * t)
    tone = (np.sin(ph) + 0.3 * np.sin(2 * ph)) * trem
    noise = np.random.randn(n); noise = noise - np.concatenate([[0], noise[:-1]])
    noise = np.convolve(noise, np.ones(6) / 6, mode="same") * trem * 0.25
    e = np.sin(np.pi * np.clip(t / dur, 0, 1)) ** 0.7
    return (tone + noise) * e * 0.14 * vel

def shimmer(vel=1.0):
    out = np.zeros(int(0.9 * SR))
    for i, m in enumerate((84, 88, 91, 96)):
        s = bell(midi(m), 0.7, 0.35)
        i0 = int(i * 0.045 * SR)
        out[i0:i0 + len(s)] += s[:len(out) - i0]
    return out * vel

# ---- 曲 ----
BPM = 96.0
BEAT = 60.0 / BPM          # 0.625
BAR = 4 * BEAT             # 2.5
T0 = 3.4
np.random.seed(11)
# 和音：C G Am F を回し、最後の2小節（bar 14, 15）は F → G で持ち上げる
prog = [("C", [60, 64, 67, 71]), ("G", [55, 59, 62, 66]), ("Am", [57, 60, 64, 67]), ("F", [53, 57, 60, 64])]
chords = [prog[b % 4] for b in range(20)]
chords[18] = ("F", [53, 57, 60, 64]); chords[19] = ("G", [55, 59, 62, 67])
pad_voicing = {"C": [48, 55, 64, 67], "G": [43, 55, 59, 62], "Am": [45, 52, 60, 64], "F": [41, 53, 57, 60]}
bass_note = {"C": 36, "G": 31, "Am": 33, "F": 29}

# 前奏：印のあと、刻みが入り始める（2.15 から：ハイハット8分と軽いキック）
put(pad([midi(m) for m in (48, 55, 62, 64)], 3.3, 0.45, attack=1.4), 0.25)
for k in range(4):
    put(hat(0.6 if k % 2 == 0 else 0.35), T0 - 2 * BEAT + k * BEAT / 2, pan=-0.2)
put(kick(0.5), T0 - 2 * BEAT); put(kick(0.6), T0 - BEAT)
put(pluck(midi(67), 0.4, 0.5), T0 - BEAT, pan=-0.2); put(pluck(midi(71), 0.4, 0.6), T0 - BEAT * 0.5, pan=0.2)
put(riser(1.0, 0.7), T0 - 1.0)


SCENE = 6.25                                     # 1場面 = 10拍
FINAL = T0 + 20 * BAR                            # 53.4
def stage_at(t):                                 # その時刻の場面番号（2..9）
    return int(min(9, 2 + (t - T0) // SCENE))
for bar in range(20):
    tb = T0 + bar * BAR
    name, tones = chords[bar]
    stage = stage_at(tb + 0.01)
    quiet = (stage == 8) and bar <= 16           # 40.9〜45.9 は静か。45.9〜48.4（bar 17）は戻りの助走
    build = (bar == 17)
    last = (bar == 19)
    vel = {2: 0.86, 3: 0.9, 4: 0.94, 5: 0.97, 6: 1.0, 7: 1.0, 8: 0.6, 9: 1.0}[stage]
    if build: vel = 0.85
    put(pad([midi(m) for m in pad_voicing[name]], BAR + 0.4, vel * (1.15 if quiet else 0.85),
            attack=(1.0 if quiet else 0.2), pump=(None if quiet else BEAT)), tb)
    if build:
        # 助走：4つ打ちのキックだけ強く、ベースは全音符、上がる息
        for k in range(4): put(kick(0.9 + 0.04 * k), tb + k * BEAT)
        put(bass(midi(bass_note[name]), 2.4, 0.7), tb)
        for beat, m in {"C": [(0, 79)], "G": [(0, 74)], "Am": [(0, 76)], "F": [(0, 72)]}[name]:
            put(bell(midi(m), 1.6, 0.6), tb + beat * BEAT, pan=0.1)
        put(riser(2.4, 0.8), tb + BAR - 2.4)
        continue
    if not quiet:
        for k in range(4):
            if last and k >= 2: break
            put(kick(0.95 if k % 2 == 0 else 0.8), tb + k * BEAT)
        if stage >= 3:
            for k in (1, 3):
                if last and k == 3: break
                put(clap(0.85 if stage < 7 else 1.0), tb + k * BEAT)
                if stage in (7, 9): put(clap(0.5), tb + k * BEAT + 0.018)
        for k in range(8):
            if last and k >= 4: break
            put(hat(0.85 if k % 2 == 0 else 0.55), tb + k * BEAT / 2, pan=-0.25)
            if stage >= 4 and k % 2 == 1:
                put(hat(0.3), tb + k * BEAT / 2 + BEAT / 4, pan=-0.25)
        if stage >= 3 and not last:
            put(hat(0.5, open_=True), tb + 3.5 * BEAT, pan=-0.25)
        if stage >= 5:
            for k in range(16):
                if last and k >= 8: break
                put(shaker(0.8 if k % 4 == 2 else 0.4), tb + k * BEAT / 4, pan=0.35)
        root = bass_note[name]
        for k in range(8):
            if last and k >= 4: break
            up = (k % 2 == 1) and stage >= 3
            put(bass(midi(root + (12 if up else 0)), 0.32, 0.9 if k % 2 == 0 else 0.7), tb + k * BEAT / 2)
        arp = tones + [tones[0] + 12, tones[1] + 12, tones[2] + 12, tones[1] + 12]
        div = 4 if stage >= 4 else 2
        for k in range(4 * div):
            if last and k >= 2 * div: break
            m = arp[k % len(arp)]
            v = (0.85 if k % 2 == 0 else 0.55) * (0.8 + 0.2 * min(1, (stage - 2) / 5.0)) * (0.8 if div == 4 else 1.0)
            put(pluck(midi(m), 0.45, v), tb + k * BEAT / div, pan=(-0.35 if k % 2 == 0 else 0.35))
        motif = {"C": [(0, 79), (1, 76), (2, 72), (3, 74)], "G": [(0, 74), (2, 71), (3, 74)],
                 "Am": [(0, 76), (1, 72), (2, 69), (3, 71)], "F": [(0, 72), (2, 76), (3, 77)]}[name]
        if stage >= 3:
            for beat, m in motif:
                if last and beat >= 2: break
                put(bell(midi(m), 1.1, 0.75 if stage < 6 else 0.85), tb + beat * BEAT, pan=0.15)
                if stage >= 6:
                    put(bell(midi(m + 4 if (m % 12) in (0, 5, 7) else m + 3), 1.0, 0.35), tb + beat * BEAT, pan=-0.15)
                if stage == 9:
                    put(bell(midi(m + 12), 1.2, 0.4), tb + beat * BEAT, pan=0.0)
        if stage in (7, 9):
            for k, m in enumerate((tones[3] + 12, tones[2] + 12, tones[3] + 12, tones[1] + 12)):
                if last and k >= 2: break
                put(pluck(midi(m), 0.4, 0.42), tb + (k + 0.5) * BEAT, pan=0.45)
            put(rim(0.6), tb + 2.5 * BEAT, pan=-0.2)
        if bar == 14:                                          # 静かな場面へ入る前の息
            put(riser(1.2, 0.6), tb + BAR - 1.2)
        if last:
            run = [60, 64, 67, 71, 72, 76, 79, 83, 84, 88]
            for k, m in enumerate(run):
                put(pluck(midi(m), 0.5, 0.4 + 0.06 * k), tb + 2 * BEAT + k * BEAT / 5, pan=(-0.4 + 0.09 * k))
            put(riser(1.25, 1.0), FINAL - 1.25)
            for k in range(4):
                put(kick(0.7 + 0.08 * k), tb + 2 * BEAT + k * BEAT / 2)
    else:
        put(bass(midi(bass_note[name]), 2.4, 0.5), tb)
        motif = {"C": [(0, 79), (2, 76)], "G": [(0, 74), (2, 71)], "Am": [(0, 76), (2, 72)], "F": [(0, 72), (2, 76)]}[name]
        for beat, m in motif:
            put(bell(midi(m), 1.8, 0.6), tb + beat * BEAT, pan=0.1)
        put(pluck(midi(tones[0] + 12), 0.8, 0.3), tb + 3 * BEAT, pan=0.2)

# 53.4：大きく温かい C（合唱ふうのパッド＋鐘の分散＋ベース）。45.2 から消え、46.6 で無音
put(kick(0.8), FINAL); put(clap(0.6), FINAL)
put(bass(midi(36), 2.6, 0.9), FINAL)
put(choir([midi(m) for m in (48, 55, 60, 64, 67, 74)], 3.2, 1.0, attack=0.06), FINAL)
put(pad([midi(m) for m in (60, 64, 67, 74, 79)], 3.0, 0.8, attack=0.05), FINAL)
for k, m in enumerate((72, 76, 79, 84, 88)):
    put(bell(midi(m), 2.2, 0.55), FINAL + 0.06 * k, pan=(-0.4 + 0.2 * k))
put(bell(midi(91), 1.8, 0.45), FINAL + 2 * BEAT, pan=0.1)        # 54.65 余韻の1音（高く）
put(bell(midi(96), 1.6, 0.3), FINAL + 3 * BEAT, pan=-0.1)
MUSIC_END = 56.6
fade = np.ones(N)
i0, i1 = int(55.2 * SR), int(MUSIC_END * SR)
fade[i0:i1] = np.cos(np.linspace(0, np.pi / 2, i1 - i0)) ** 1.4
fade[i1:] = 0.0
L *= fade; R *= fade
# 頂点（28.4〜33.4）と締め（38.4〜43.4）は1割上げる
lift = np.ones(N)
for a, b in ((34.65, 40.9), (48.4, 53.4)):
    ia, ib = int(a * SR), int(b * SR); ramp = int(0.4 * SR)
    lift[ia:ib] = 1.12
    lift[ia:ia + ramp] = 1 + 0.12 * np.linspace(0, 1, ramp)
    lift[ib - ramp:ib] = 1 + 0.12 * np.linspace(1, 0, ramp)
L *= lift; R *= lift

# ---- 効果音（印）----
POKON = (0.50, 57.01)
WHIRR = (0.53, 57.03)
SHIMMER = (1.22, 57.72)
for t in POKON: put(pokon(1.0), t)
for t in WHIRR: put(whirr(0.95, 1.0), t, pan=0.1)
for t in SHIMMER: put(shimmer(0.8), t, pan=0.2)

# ---- 仕上げ ----
mix = np.stack([L, R])
fade_in = np.clip(t_all / 0.15, 0, 1)
fade_out = np.clip((DUR - t_all) / 0.8, 0, 1)
mix *= fade_in * fade_out
peak = np.abs(mix).max()
mix = mix / peak * 0.89
mix = np.tanh(mix * 1.2) / np.tanh(1.2)
mix = mix / np.abs(mix).max() * 0.92
with wave.open(sys.argv[1] if len(sys.argv) > 1 else "bgm3.wav", "wb") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    inter = (np.stack([mix[0], mix[1]], axis=1) * 32767).astype(np.int16)
    w.writeframes(inter.tobytes())
print("wrote", DUR, "s  peak", float(np.abs(mix).max()), " pokon at", POKON)
