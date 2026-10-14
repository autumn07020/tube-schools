# -*- coding: utf-8 -*-
"""紹介動画（52秒版）の音。BGM ＋ 印が弾む音（ぽこん）＋ 輪が回る音。numpy だけで合成する。

動画の時刻（描いたコマから測った）
  0.30  印が現れる → 0.47〜0.63 いちばん大きい（弾みの山）→ 0.53〜1.50 白い輪が描かれる → 1.2〜1.9 銘
  3.4 / 8.4 / 13.6 / 18.6 / 23.6 / 27.0  場面が変わる
  27.00 印が現れる → 27.07〜27.23 山 → 27.13〜28.1 輪 → 27.8〜28.5 銘 → 29.4 薄れる
BGM は 96 BPM（1小節 2.5秒）で、3.4秒を小節の頭にすると場面の変わり目がほぼ小節の頭に乗る。
"""
import numpy as np, wave, sys, os

SR = 44100
DUR = 52.0
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
    click = np.random.randn(n) * np.exp(-t / 0.002) * 0.25
    return (np.sin(ph) * np.exp(-t / 0.12) + click) * 0.62 * vel

def shaker(vel=1.0):
    n = int(0.07 * SR)
    x = np.random.randn(n)
    x = x - np.concatenate([[0], x[:-1]])                  # 高い方だけ残す
    e = np.exp(-np.arange(n) / SR / 0.018)
    return x * e * 0.045 * vel

def clap(vel=1.0):
    """手拍子ふう：短い雑音の束を3つ重ねる（2拍・4拍）"""
    n = int(0.11 * SR)
    out = np.zeros(n)
    for k, d in enumerate((0.0, 0.011, 0.022)):
        x = np.random.randn(n)
        x = np.convolve(x, np.ones(5) / 5, mode="same") - np.convolve(x, np.ones(40) / 40, mode="same")
        e = np.exp(-np.arange(n) / SR / (0.03 + 0.01 * k))
        i0 = int(d * SR)
        out[i0:] += (x * e)[:n - i0]
    return out * 0.16 * vel

def hat(vel=1.0, open_=False):
    """閉じたハイハット（8分・16分の刻み）"""
    n = int((0.09 if open_ else 0.035) * SR)
    x = np.random.randn(n)
    x = x - np.concatenate([[0], x[:-1]]); x = x - np.concatenate([[0], x[:-1]])
    e = np.exp(-np.arange(n) / SR / (0.05 if open_ else 0.012))
    return x * e * 0.05 * vel

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
# 52秒版。展開：場面ごとに層が増え、保護者の場面で頂点 → 「でも大事にしています」で一度静かに → 最後にまた盛り上がってジャーン。
#   3.4  S2 生徒が出す        弾き音＋パッド＋軽い刻み（キック1拍）
#   8.4  S3 今日やること      ＋ベース、キック1・3拍、4拍にクラップ
#  13.4  S4 なぞるだけ        ＋鐘のメロディ、クラップ2・4拍、ハイハット8分
#  18.4  S5 iPadで赤          ＋ベースの上がり、ハイハット16分の走り、リム
#  23.4  S6 一人ひとりの宿題  ＋鐘の3度重ね、シェイカー16分
#  28.4  S7 保護者            頂点：高い弾き音の対旋律、クラップ2つ重ね、終わりに上がる息
#  33.4  S8 プライバシー      静かに：打楽器を抜き、パッドと鐘だけ（「でも、これも大事に」）
#  38.4  S9 アナログのまま    もう一度全部、最後の2拍で連符 → 43.4 ジャーン
#  43.4  弱いジャーン → 46.6 で無音 → 46.9 印（ぽこん・輪・銘）
BPM = 96.0
BEAT = 60.0 / BPM          # 0.625
BAR = 4 * BEAT             # 2.5
T0 = 3.4
chords = [("C", [60, 64, 67, 71]), ("G", [55, 59, 62, 66]), ("Am", [57, 60, 64, 67]), ("F", [53, 57, 60, 64])]
pad_voicing = {"C": [48, 55, 64, 67], "G": [43, 55, 59, 62], "Am": [45, 52, 60, 64], "F": [41, 53, 57, 60]}
bass_note = {"C": 36, "G": 31, "Am": 33, "F": 29}
np.random.seed(7)

put(pad([midi(m) for m in (48, 55, 62, 64)], 3.3, 0.5, attack=1.6), 0.25)
put(pluck(midi(67), 0.5, 0.55), T0 - BEAT, pan=-0.2)
put(pluck(midi(71), 0.5, 0.65), T0 - BEAT * 0.5, pan=0.2)

FINAL = T0 + 16 * BAR      # 43.4
for bar in range(16):
    tb = T0 + bar * BAR
    name, tones = chords[bar % 4]
    stage = bar // 2 + 2                       # 2..9 ＝ 場面
    quiet = (stage == 8)                       # プライバシー：静かに
    vel = {2: 0.7, 3: 0.78, 4: 0.86, 5: 0.92, 6: 0.96, 7: 1.0, 8: 0.6, 9: 1.0}[stage]
    last_fill = (bar == 15)
    # パッド
    put(pad([midi(m) for m in pad_voicing[name]], BAR + 0.4, vel * (1.1 if quiet else 0.9), attack=(0.9 if quiet else 0.35)), tb)
    # アルペジオ：8分。頂点と締めは強拍を1オクターブ上に重ねる
    arp = tones + [tones[0] + 12, tones[1] + 12, tones[2] + 12, tones[1] + 12]
    for k in range(8):
        if last_fill and k >= 4: break
        if quiet and k % 2: continue           # 静かな場面は4分で
        m = arp[k % len(arp)]
        v = (0.9 if k % 2 == 0 else 0.62) * (0.8 + 0.2 * min(1, (stage - 2) / 5.0)) * (0.7 if quiet else 1)
        put(pluck(midi(m), 0.55, v), tb + k * BEAT / 2, pan=(-0.35 if k % 2 == 0 else 0.35))
        if stage in (6, 7, 9) and k % 2 == 0:
            put(pluck(midi(m + 12), 0.5, 0.35), tb + k * BEAT / 2, pan=0.0)
    # ベース：場面3から（静かな場面は長く1つ）
    if stage >= 3:
        if quiet:
            put(bass(midi(bass_note[name]), 2.4, 0.55), tb)
        else:
            put(bass(midi(bass_note[name]), 1.25, 0.9), tb)
            put(bass(midi(bass_note[name]), 1.25, 0.7), tb + 2 * BEAT)
            if stage >= 5:
                put(bass(midi(bass_note[name] + 12), 0.4, 0.45), tb + 3.5 * BEAT)
            if stage in (7, 9):
                put(bass(midi(bass_note[name]), 0.5, 0.5), tb + 1.5 * BEAT)
    # 打楽器
    if stage == 2:
        put(kick(0.55), tb)
        for k in range(8):
            put(shaker(0.7 if k % 2 else 0.35), tb + k * BEAT / 2, pan=0.3)
    elif not quiet:
        put(kick(0.75 if stage == 3 else 0.9), tb)
        put(kick(0.6 if stage == 3 else 0.8), tb + 2 * BEAT)
        if stage >= 5: put(kick(0.5), tb + 1.5 * BEAT)                       # 2拍の裏で前へ
        div = 4 if stage >= 6 else 2
        for k in range(4 * div):
            if last_fill and k >= 2 * div: break
            put(shaker((0.85 if k % 2 else 0.45) * (0.8 if div == 4 else 1.0)), tb + k * BEAT / div, pan=0.3)
        if stage >= 4:
            for k in range(8):
                if last_fill and k >= 4: break
                put(hat(0.8 if k % 2 == 0 else 0.5), tb + k * BEAT / 2, pan=-0.25)
            if stage >= 5:                                                   # 4拍目に16分の走り
                for k in range(4):
                    if last_fill: break
                    put(hat(0.45), tb + 3 * BEAT + k * BEAT / 4, pan=-0.25)
        if stage >= 3:
            if stage == 3:
                put(clap(0.6), tb + 3 * BEAT)
            else:
                put(clap(0.8 if stage < 7 else 0.95), tb + BEAT)
                if not last_fill: put(clap(0.8 if stage < 7 else 0.95), tb + 3 * BEAT)
                if stage in (7, 9):
                    put(clap(0.5), tb + BEAT + 0.02); put(clap(0.5), tb + 3 * BEAT + 0.02)
        if stage >= 5:
            put(rim(0.6), tb + 2.5 * BEAT, pan=-0.2)
    else:
        put(kick(0.35), tb)                                                  # 静かな場面：1拍だけ
    # 鐘のメロディ：場面4から。6以降は3度上を薄く重ねる。静かな場面はゆっくり2音
    motif = {"C": [(0, 79), (1, 76), (2, 72), (3, 74)], "G": [(0, 74), (2, 71), (3, 74)],
             "Am": [(0, 76), (1, 72), (2, 69), (3, 71)], "F": [(0, 72), (2, 76), (3, 77)]}[name]
    if quiet:
        for beat, m in motif[:2]:
            put(bell(midi(m), 1.6, 0.6), tb + beat * 2 * BEAT, pan=0.1)
    elif stage >= 4:
        for beat, m in motif:
            if last_fill and beat >= 2: break
            put(bell(midi(m), 1.1, 0.7 if stage == 4 else 0.8), tb + beat * BEAT, pan=0.15)
            if stage >= 6:
                put(bell(midi(m + 4 if (m % 12) in (0, 5, 7) else m + 3), 1.0, 0.35), tb + beat * BEAT, pan=-0.15)
    # 頂点（場面7）と締め（場面9）：高い弾き音の対旋律（裏拍）
    if stage in (7, 9):
        for k, m in enumerate((tones[3] + 12, tones[2] + 12, tones[3] + 12, tones[1] + 12)):
            if last_fill and k >= 2: break
            put(pluck(midi(m), 0.4, 0.4), tb + (k + 0.5) * BEAT, pan=0.45)
    # 場面7の終わり：上がる息（次の静かな場面へ落とす前に、ふっと）
    if bar == 11:
        n = int(1.0 * SR); t = np.arange(n) / SR
        noise = np.random.randn(n); noise = noise - np.concatenate([[0], noise[:-1]])
        put(noise * (t / 1.0) ** 2.0 * 0.035, tb + BAR - 1.0)
    # 最後の2拍：上がる連符と息 → ジャーン
    if last_fill:
        run = [60, 64, 67, 71, 72, 76, 79, 83]
        for k, m in enumerate(run):
            put(pluck(midi(m), 0.5, 0.45 + 0.07 * k), tb + 2 * BEAT + k * BEAT / 4, pan=(-0.4 + 0.11 * k))
        n = int(1.2 * SR); t = np.arange(n) / SR
        noise = np.random.randn(n); noise = noise - np.concatenate([[0], noise[:-1]])
        put(noise * (t / 1.2) ** 2.2 * 0.05, FINAL - 1.2, pan=0.0)

# 弱いジャーン：C の和音。2.6秒でゆっくり消え、46.6 で無音
put(kick(0.6), FINAL)
put(clap(0.5), FINAL)
put(bass(midi(36), 2.4, 0.8), FINAL)
put(pad([midi(m) for m in (48, 55, 64, 67, 74)], 3.0, 1.0, attack=0.05), FINAL)
for k, m in enumerate((72, 76, 79, 86)):
    put(bell(midi(m), 2.2, 0.55), FINAL + 0.012 * k, pan=(-0.3 + 0.2 * k))
put(bell(midi(84), 1.6, 0.35), FINAL + 2 * BEAT, pan=0.1)
MUSIC_END = 46.6
fade = np.ones(N)
i0, i1 = int(44.9 * SR), int(MUSIC_END * SR)
fade[i0:i1] = np.cos(np.linspace(0, np.pi / 2, i1 - i0)) ** 1.5
fade[i1:] = 0.0
L *= fade; R *= fade
# 頂点（保護者 28.4〜33.4）と締め（38.4〜43.4）は1割だけ持ち上げる（前後 0.4 秒でなだらかに）
lift = np.ones(N)
for a, b in ((28.4, 33.4), (38.4, 43.4)):
    ia, ib = int(a * SR), int(b * SR); ramp = int(0.4 * SR)
    lift[ia:ib] = 1.12
    lift[ia:ia + ramp] = 1 + 0.12 * np.linspace(0, 1, ramp)
    lift[ib - ramp:ib] = 1 + 0.12 * np.linspace(1, 0, ramp)
L *= lift; R *= lift

# ---- 効果音（動画の時刻に合わせる）----
POKON = (0.50, 47.01)          # 印が弾む山（0.47〜0.63 / 27.07〜27.23）の少し手前で鳴り始める
WHIRR = (0.53, 47.03)          # 輪が描かれ始める時刻
SHIMMER = (1.22, 47.72)        # 銘が出る
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
