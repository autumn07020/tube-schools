# -*- coding: utf-8 -*-
"""紹介動画（30秒）の音。BGM ＋ 印が弾む音（ぽこん）＋ 輪が回る音。numpy だけで合成する。

動画の時刻（描いたコマから測った）
  0.30  印が現れる → 0.47〜0.63 いちばん大きい（弾みの山）→ 0.53〜1.50 白い輪が描かれる → 1.2〜1.9 銘
  3.4 / 8.4 / 13.6 / 18.6 / 23.6 / 27.0  場面が変わる
  27.00 印が現れる → 27.07〜27.23 山 → 27.13〜28.1 輪 → 27.8〜28.5 銘 → 29.4 薄れる
BGM は 96 BPM（1小節 2.5秒）で、3.4秒を小節の頭にすると場面の変わり目がほぼ小節の頭に乗る。
"""
import numpy as np, wave, sys, os

SR = 44100
DUR = 30.0
N = int(SR * DUR)
L = np.zeros(N); R = np.zeros(N)
t_all = np.arange(N) / SR

def put(sig, t0, pan=0.0, gain=1.0):
    """sig を t0 秒から重ねる。pan は -1（左）〜1（右）"""
    i0 = int(t0 * SR)
    if i0 >= N: return
    seg = sig[:N - i0] * gain
    gl = np.sqrt(0.5 * (1 - pan)); gr = np.sqrt(0.5 * (1 + pan))
    L[i0:i0 + len(seg)] += seg * gl
    R[i0:i0 + len(seg)] += seg * gr

def env_adsr(n, a, d, s, r, sr=SR):
    a_n, d_n, r_n = int(a * sr), int(d * sr), int(r * sr)
    e = np.ones(n)
    a_n = min(a_n, n); e[:a_n] = np.linspace(0, 1, a_n, endpoint=False) if a_n else e[:0]
    if d_n and a_n + d_n <= n: e[a_n:a_n + d_n] = np.linspace(1, s, d_n); e[a_n + d_n:] = s
    elif a_n < n: e[a_n:] = s
    r_n = min(r_n, n)
    if r_n: e[-r_n:] *= np.linspace(1, 0, r_n)
    return e

def midi(m): return 440.0 * 2 ** ((m - 69) / 12.0)

# ---- 音色 ----
def pluck(f, dur=0.6, vel=1.0):
    n = int(dur * SR); t = np.arange(n) / SR
    w = (np.sin(2 * np.pi * f * t) + 0.35 * np.sin(2 * np.pi * 2 * f * t + 0.3) + 0.12 * np.sin(2 * np.pi * 3 * f * t)
         + 0.08 * np.sin(2 * np.pi * f * 1.004 * t))
    e = np.exp(-t / 0.22) * (1 - np.exp(-t / 0.004))
    return w * e * 0.22 * vel

def bell(f, dur=1.2, vel=1.0):
    n = int(dur * SR); t = np.arange(n) / SR
    w = np.sin(2 * np.pi * f * t) + 0.5 * np.sin(2 * np.pi * 2.0 * f * t) * np.exp(-t / 0.3) + 0.25 * np.sin(2 * np.pi * 3.01 * f * t) * np.exp(-t / 0.15)
    e = np.exp(-t / 0.45) * (1 - np.exp(-t / 0.003))
    return w * e * 0.18 * vel

def pad(freqs, dur, vel=1.0, attack=0.9):
    n = int(dur * SR); t = np.arange(n) / SR
    w = np.zeros(n)
    for f in freqs:
        for k, det in ((1, 0.0), (1, 0.0025), (1, -0.0025)):
            w += np.sin(2 * np.pi * f * (1 + det) * t + np.random.rand() * 6.28)
        w += 0.35 * np.sin(2 * np.pi * 2 * f * t) + 0.12 * np.sin(2 * np.pi * 3 * f * t)
    w /= (len(freqs) * 3.5)
    # ゆっくり開く（LFO）
    w *= 1 + 0.08 * np.sin(2 * np.pi * 0.35 * t)
    e = env_adsr(n, attack, 0.3, 0.85, min(0.6, dur / 3))
    return w * e * 0.20 * vel

def bass(f, dur=1.2, vel=1.0):
    n = int(dur * SR); t = np.arange(n) / SR
    w = np.sin(2 * np.pi * f * t) + 0.25 * np.sin(2 * np.pi * 2 * f * t) * np.exp(-t / 0.3)
    e = env_adsr(n, 0.01, 0.2, 0.75, 0.15)
    return w * e * 0.30 * vel

def kick(vel=1.0):
    n = int(0.28 * SR); t = np.arange(n) / SR
    f = 42 + 90 * np.exp(-t / 0.045)
    ph = 2 * np.pi * np.cumsum(f) / SR
    return np.sin(ph) * np.exp(-t / 0.11) * 0.55 * vel

def shaker(vel=1.0):
    n = int(0.07 * SR)
    x = np.random.randn(n)
    x = x - np.concatenate([[0], x[:-1]])                  # 高い方だけ残す
    e = np.exp(-np.arange(n) / SR / 0.018)
    return x * e * 0.045 * vel

def rim(vel=1.0):
    n = int(0.03 * SR)
    x = np.random.randn(n)
    x = np.convolve(x, np.ones(3) / 3, mode="same") - np.convolve(x, np.ones(12) / 12, mode="same")
    e = np.exp(-np.arange(n) / SR / 0.007)
    return x * e * 0.12 * vel

# ---- 効果音 ----
def pokon(vel=1.0):
    """ぽこん：短く上がる「ぽ」と、少し高く鳴って消える「こん」"""
    n = int(0.36 * SR); t = np.arange(n) / SR
    f1 = 330 + (760 - 330) * np.clip(t / 0.055, 0, 1)             # 上へすっと
    ph1 = 2 * np.pi * np.cumsum(f1) / SR
    po = np.sin(ph1) * np.exp(-t / 0.05) * (1 - np.exp(-t / 0.002))
    t2 = np.clip(t - 0.05, 0, None)
    f2 = 1046.5 * (1 - 0.06 * np.clip(t2 / 0.12, 0, 1))          # こん：C6 からわずかに下がる
    ph2 = 2 * np.pi * np.cumsum(f2) / SR
    kon = (np.sin(ph2) + 0.4 * np.sin(2 * ph2) * np.exp(-t2 / 0.05)) * np.exp(-t2 / 0.11) * (t >= 0.05) * (1 - np.exp(-t2 / 0.002))
    return (po * 0.9 + kon * 0.7) * 0.55 * vel

def whirr(dur=0.95, vel=1.0):
    """輪が回って描かれる音：細い音が上がりながら、回転のように揺れる"""
    n = int(dur * SR); t = np.arange(n) / SR
    f = 520 * (1.0 + 1.9 * (t / dur) ** 0.8)
    ph = 2 * np.pi * np.cumsum(f) / SR
    trem = 0.55 + 0.45 * np.sin(2 * np.pi * (14 + 10 * t / dur) * t)       # 回る感じ（だんだん速く）
    tone = (np.sin(ph) + 0.3 * np.sin(2 * ph)) * trem
    noise = np.random.randn(n); noise = noise - np.concatenate([[0], noise[:-1]])
    noise = np.convolve(noise, np.ones(6) / 6, mode="same") * trem * 0.25
    e = np.sin(np.pi * np.clip(t / dur, 0, 1)) ** 0.7                     # 山なり
    return (tone + noise) * e * 0.14 * vel

def shimmer(vel=1.0):
    """銘が出る：きらっと上がる4音"""
    out = np.zeros(int(0.9 * SR))
    for i, m in enumerate((84, 88, 91, 96)):
        s = bell(midi(m), 0.7, 0.35)
        i0 = int(i * 0.045 * SR)
        out[i0:i0 + len(s)] += s[:len(out) - i0]
    return out * vel

# ---- 曲 ----
# 展開：場面ごとに1つずつ層が増える（これもできます → こんなのも → そしてこれも！）。
#   場面2 3.4〜  弾き音のアルペジオ＋パッド（打楽器なし）
#   場面3 8.4〜  ベースと、軽いキック（1・3拍）・シェイカー
#   場面4 13.6〜 鐘のメロディ
#   場面5 18.6〜 いちばん厚く：鐘に3度の重ね、シェイカー16分、リム。最後の2拍で上がる連符
#   場面6 23.4   弱く「ジャーン」（C の和音）→ ゆっくり消えて、26.7 で無音
#   27.0〜       音楽は無し。印の「ぽこん」と輪の音だけ
BPM = 96.0
BEAT = 60.0 / BPM          # 0.625
BAR = 4 * BEAT             # 2.5
T0 = 3.4                   # 小節の頭
chords = [("C", [60, 64, 67, 71]), ("G", [55, 59, 62, 66]), ("Am", [57, 60, 64, 67]), ("F", [53, 57, 60, 64])]
pad_voicing = {"C": [48, 55, 64, 67], "G": [43, 55, 59, 62], "Am": [45, 52, 60, 64], "F": [41, 53, 57, 60]}
bass_note = {"C": 36, "G": 31, "Am": 33, "F": 29}
np.random.seed(7)

# 前奏：静かなパッド（0.3 から）と、さきがけの2音
put(pad([midi(m) for m in (48, 55, 62, 64)], 3.3, 0.5, attack=1.6), 0.25)
put(pluck(midi(67), 0.5, 0.55), T0 - BEAT, pan=-0.2)
put(pluck(midi(71), 0.5, 0.65), T0 - BEAT * 0.5, pan=0.2)

FINAL = T0 + 8 * BAR       # 23.4：弱いジャーン
for bar in range(8):
    tb = T0 + bar * BAR
    name, tones = chords[bar % 4]
    stage = bar // 2 + 2                       # 2,3,4,5 ＝ 場面の番号
    vel = {2: 0.7, 3: 0.8, 4: 0.9, 5: 1.0}[stage]
    # パッド
    put(pad([midi(m) for m in pad_voicing[name]], BAR + 0.4, vel * 0.9, attack=0.35), tb)
    # アルペジオ：8分音符。場面5は強拍を1オクターブ上に重ねる
    arp = tones + [tones[0] + 12, tones[1] + 12, tones[2] + 12, tones[1] + 12]
    last_fill = (bar == 7)
    for k in range(8):
        if last_fill and k >= 4: break         # 最後の2拍は連符に譲る
        m = arp[k % len(arp)]
        v = (0.9 if k % 2 == 0 else 0.62) * (0.85 + 0.15 * (stage - 2) / 3)
        put(pluck(midi(m), 0.55, v), tb + k * BEAT / 2, pan=(-0.35 if k % 2 == 0 else 0.35))
        if stage == 5 and k % 2 == 0:
            put(pluck(midi(m + 12), 0.5, 0.35), tb + k * BEAT / 2, pan=0.0)
    # ベース：場面3から
    if stage >= 3:
        put(bass(midi(bass_note[name]), 1.25, 0.9), tb)
        put(bass(midi(bass_note[name]), 1.25, 0.7), tb + 2 * BEAT)
        if stage == 5:                          # 4拍目の裏で1オクターブ上へ（前へ進む感じ）
            put(bass(midi(bass_note[name] + 12), 0.4, 0.45), tb + 3.5 * BEAT)
    # 打楽器：場面3からキック1・3拍とシェイカー8分。場面4でリム。場面5でシェイカー16分
    if stage >= 3:
        put(kick(0.7 if stage == 3 else 0.85), tb)
        put(kick(0.55 if stage == 3 else 0.7), tb + 2 * BEAT)
        div = 4 if stage == 5 else 2
        for k in range(4 * div):
            if last_fill and k >= 2 * div: break
            put(shaker((0.85 if k % 2 else 0.45) * (0.8 if div == 4 else 1.0)), tb + k * BEAT / div, pan=0.3)
    if stage >= 4:
        put(rim(0.5 if stage == 4 else 0.7), tb + BEAT, pan=-0.2)
        if not last_fill: put(rim(0.5 if stage == 4 else 0.7), tb + 3 * BEAT, pan=-0.2)
    # 鐘のメロディ：場面4から。場面5は3度上を薄く重ねる
    if stage >= 4:
        motif = {"C": [(0, 79), (1, 76), (2, 72), (3, 74)], "G": [(0, 74), (2, 71), (3, 74)],
                 "Am": [(0, 76), (1, 72), (2, 69), (3, 71)], "F": [(0, 72), (2, 76), (3, 77)]}[name]
        for beat, m in motif:
            if last_fill and beat >= 2: break
            put(bell(midi(m), 1.1, 0.7 if stage == 4 else 0.8), tb + beat * BEAT, pan=0.15)
            if stage == 5:
                put(bell(midi(m + 4 if (m % 12) in (0, 5, 7) else m + 3), 1.0, 0.35), tb + beat * BEAT, pan=-0.15)
    # 最後の2拍：上がる連符と、息を吸うような細い揺らぎ → ジャーンへ
    if last_fill:
        run = [60, 64, 67, 71, 72, 76, 79, 83]
        for k, m in enumerate(run):
            put(pluck(midi(m), 0.5, 0.45 + 0.07 * k), tb + 2 * BEAT + k * BEAT / 4, pan=(-0.4 + 0.11 * k))
        n = int(1.2 * SR); t = np.arange(n) / SR
        noise = np.random.randn(n); noise = noise - np.concatenate([[0], noise[:-1]])
        put(noise * (t / 1.2) ** 2.2 * 0.05, FINAL - 1.2, pan=0.0)

# 弱いジャーン：C の和音（パッド＋鐘＋ベース＋軽いキック）。2.6秒でゆっくり消え、26.7 で無音
put(kick(0.5), FINAL)
put(bass(midi(36), 2.4, 0.8), FINAL)
put(pad([midi(m) for m in (48, 55, 64, 67, 74)], 3.0, 1.0, attack=0.05), FINAL)
for k, m in enumerate((72, 76, 79, 86)):
    put(bell(midi(m), 2.2, 0.55), FINAL + 0.012 * k, pan=(-0.3 + 0.2 * k))
put(bell(midi(84), 1.6, 0.35), FINAL + 2 * BEAT, pan=0.1)     # 余韻の1音（24.65）
# 24.9 から 26.6 にかけて音楽を消し、27.0 の直前は無音にする
MUSIC_END = 26.7
fade = np.ones(N)
i0, i1 = int(24.9 * SR), int(MUSIC_END * SR)
fade[i0:i1] = np.cos(np.linspace(0, np.pi / 2, i1 - i0)) ** 1.5
fade[i1:] = 0.0
L *= fade; R *= fade

# ---- 効果音（動画の時刻に合わせる）----
POKON = (0.50, 27.11)          # 印が弾む山（0.47〜0.63 / 27.07〜27.23）の少し手前で鳴り始める
WHIRR = (0.53, 27.13)          # 輪が描かれ始める時刻
SHIMMER = (1.22, 27.82)        # 銘が出る
for t in POKON: put(pokon(1.0), t)
for t in WHIRR: put(whirr(0.95, 1.0), t, pan=0.1)
for t in SHIMMER: put(shimmer(0.8), t, pan=0.2)

# ---- 仕上げ ----
mix = np.stack([L, R])
# 頭と終わりを整える
fade_in = np.clip(t_all / 0.15, 0, 1)
fade_out = np.clip((DUR - t_all) / 0.8, 0, 1)
mix *= fade_in * fade_out
# やわらかいリミッター
peak = np.abs(mix).max()
mix = mix / peak * 0.89
mix = np.tanh(mix * 1.15) / np.tanh(1.15)
mix = mix / np.abs(mix).max() * 0.92
with wave.open(sys.argv[1] if len(sys.argv) > 1 else "bgm.wav", "wb") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    inter = (np.stack([mix[0], mix[1]], axis=1) * 32767).astype(np.int16)
    w.writeframes(inter.tobytes())
print("wrote", DUR, "s  peak", float(np.abs(mix).max()), " pokon at", POKON, "whirr at", WHIRR)
