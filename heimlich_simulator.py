"""
哈姆立克：黃金三分鐘  v4.0  (Pro Optimized - 極致效能版)
─────────────────────────────────────────────────
優化核心：
  1. 事件過濾 (Event Filtering)：阻斷無效滑鼠軌跡，解放 CPU。
  2. Sprite 粒子群組：整合 C 語言底層加速的群組渲染與 Alpha 預渲染快取。
  3. 記憶體自動回收：Sprite.kill() 確保資源完美釋放。
"""

import pygame, sys, random, math, array, functools, os

# 【架構優化】快取清除回調列表 —— 避免在 LogicalScreen 中使用 globals() 反模式
_CACHE_INVALIDATORS = []

pygame.mixer.pre_init(44100, -16, 2, 512)
pygame.init()
pygame.font.init()

# 【效能優化】阻斷不必要的事件 (如 MouseMotion)，大幅降低 CPU 負載
pygame.event.set_allowed([pygame.QUIT, pygame.VIDEORESIZE, pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP])

# ── Configuration ─────────────────────────────────────────────────────────────
BASE_W, BASE_H = 1140, 760
cur_w, cur_h = BASE_W, BASE_H

class LogicalScreen:
    """處理邏輯座標 (1140x760) 與實際視窗座標的映射"""
    scale = 1.0
    off_x = 0
    off_y = 0

    @classmethod
    def update(cls, w, h):
        w, h = max(1, w), max(1, h)
        cls.scale = max(0.01, min(w / BASE_W, h / BASE_H))
        cls.off_x = (w - BASE_W * cls.scale) // 2
        cls.off_y = (h - BASE_H * cls.scale) // 2
        # 【優化】透過回調清除下游快取，取代 globals() 反模式
        for _inv in _CACHE_INVALIDATORS:
            _inv()

    @classmethod
    def to_screen(cls, x, y):
        return (int(x * cls.scale + cls.off_x), int(y * cls.scale + cls.off_y))

    @classmethod
    def to_world(cls, x, y):
        return (int((x - cls.off_x) / cls.scale), int((y - cls.off_y) / cls.scale))

    @classmethod
    def s(cls, val):
        return int(val * cls.scale)

try:
    # 執行時預設為「最大化視窗」(保留標題列與工作列)
    screen = pygame.display.set_mode((BASE_W, BASE_H), pygame.RESIZABLE | pygame.WINDOWMAXIMIZED)
except Exception:
    screen = pygame.display.set_mode((BASE_W, BASE_H), pygame.RESIZABLE)

# 初始同步解析度至邏輯座標系統
LogicalScreen.update(screen.get_width(), screen.get_height())

pygame.display.set_caption("哈姆立克：黃金三分鐘 v4.0 (極致效能版)")
clock = pygame.time.Clock()
FPS   = 60

# ── Palette ───────────────────────────────────────────────────────────────────
C = dict(
    bg       = (4,   9,  22),
    panel    = (13,  21, 40),
    panel2   = (18,  28, 48),
    text     = (224, 230, 240),
    orange   = (249, 115, 22),
    amber    = (245, 158, 11),
    cyan     = (6,   182, 212),
    emerald  = (52,  211, 153),
    red      = (239, 68,  68),
    red2     = (180, 28,  28),
    fuchsia  = (217, 70,  239),
    pink     = (236, 72,  153),
    gold     = (251, 191, 36),
    white    = (255, 255, 255),
    s400     = (148, 163, 184),
    s500     = (95,  110, 130),
    s600     = (70,  83,  104),
    s700     = (50,  62,  84),
    s800     = (28,  40,  58),
    s900     = (13,  21,  40),
    s950     = (4,   9,   22),
    body     = (52,  62,  78),
    body2    = (72,  83,  98),
)

# ── Fonts & Caching ───────────────────────────────────────────────────────────
@functools.lru_cache(maxsize=64)
def load_font(size, bold=False):
    for name in ["Microsoft JhengHei", "Arial Unicode MS", "Noto Sans TC"]:
        try: return pygame.font.SysFont(name, size, bold=bold)
        except: continue
    return pygame.font.SysFont(None, size, bold=bold)

_TEXT_CACHE = {}

@functools.lru_cache(maxsize=512)
def get_text_surf(text, font, col):
    return font.render(text, True, col)

def tc(surf, text, font, col, cx, cy, use_cache=True):
    if use_cache:
        s = get_text_surf(text, font, col)
    else:
        s = font.render(text, True, col)
    surf.blit(s, s.get_rect(center=(cx, cy)))

def tl(surf, text, font, col, x, y, use_cache=True):
    if use_cache:
        s = get_text_surf(text, font, col)
    else:
        s = font.render(text, True, col)
    surf.blit(s, (x, y))

F48 = load_font(85, True); F36 = load_font(70, True); F28 = load_font(58, True)
F22 = load_font(48, True); F18 = load_font(38); F15 = load_font(28, True); F13 = load_font(20, True)

# ── Synthesised Sound ─────────────────────────────────────────────────────────
RATE = 44100

def _mk_buf(frames):
    try:
        conf = pygame.mixer.get_init()
        if conf is None: return None # 預防音訊設備未初始化
        channels = conf[2]
        arr = array.array("h", frames)
        if channels == 2:
            stereo = array.array("h")
            for x in arr: stereo.extend([x, x])
            return pygame.mixer.Sound(buffer=stereo.tobytes())
        return pygame.mixer.Sound(buffer=arr.tobytes())
    except Exception: return None

def _synth(freq, dur, wave="sin", attack=0.01, decay=0.12, vol=0.45):
    n = int(RATE * dur); buf = []
    for i in range(n):
        t = i / RATE
        if wave == "sin": v = math.sin(2*math.pi*freq*t)
        elif wave == "sq": v = 1.0 if math.sin(2*math.pi*freq*t) > 0 else -1.0
        elif wave == "noise": v = random.uniform(-1,1)
        else: v = math.sin(2*math.pi*freq*t)
        a_s = min(t/attack,1.0) if attack > 0 else 1.0
        d_s = max(0.0, 1.0-(t-attack)/decay) if t > attack else 1.0
        buf.append(int(v * a_s * d_s * vol * 32767))
    return _mk_buf(buf)

def _thump():
    n = int(RATE*0.18); buf = []
    for i in range(n):
        t = i/RATE
        f = 120*math.exp(-t*30)
        v = math.sin(2*math.pi*f*t) + random.uniform(-0.3,0.3)*0.4
        env = math.exp(-t*18)
        buf.append(int(v*env*0.55*32767))
    return _mk_buf(buf)

def _alarm():
    n = int(RATE*0.25); buf = []
    for i in range(n):
        t = i/RATE
        f = 880 + 440*math.sin(2*math.pi*6*t)
        v = math.sin(2*math.pi*f*t)*math.exp(-t*4)*0.35
        buf.append(int(v*32767))
    return _mk_buf(buf)

def _success():
    buf = []
    for note,dur in [(523,0.12),(659,0.12),(784,0.20)]:
        nn = int(RATE*dur)
        for i in range(nn):
            t = i/RATE
            v = math.sin(2*math.pi*note*t)*math.exp(-t*6)*0.45
            buf.append(int(v*32767))
    return _mk_buf(buf)

def _hover_sound():
    # 極短的電子滴答聲
    n = int(RATE*0.04); buf = []
    for i in range(n):
        t = i/RATE
        v = math.sin(2*math.pi*1200*t)*math.exp(-t*80)*0.25
        buf.append(int(v*32767))
    return _mk_buf(buf)

def _click_sound():
    # 升調的確認提示音
    buf = []
    for note,dur in [(660,0.06),(880,0.08)]:
        nn = int(RATE*dur)
        for i in range(nn):
            t = i/RATE; v = math.sin(2*math.pi*note*t)*math.exp(-t*15)*0.35
            buf.append(int(v*32767))
    return _mk_buf(buf)

def _fail_sound():
    n = int(RATE*0.30); buf = []
    for i in range(n):
        t = i/RATE
        f = max(60, 250-200*t)
        v = math.sin(2*math.pi*f*t)*math.exp(-t*6)*0.4
        buf.append(int(v*32767))
    return _mk_buf(buf)

SND_THUMP = SND_PERFECT = SND_GOOD = SND_FAIL = SND_SUCCESS = SND_ALARM = SND_CHARGE = SND_HOVER = SND_CLICK = None
SOUND_OK = False

def resource_path(rel):
    if getattr(sys, 'frozen', False): return os.path.join(sys._MEIPASS, rel)
    # 使用 __file__ 確保在不同路徑執行時依然能定位到檔案
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), rel)

try:
    path_hit = resource_path("hit.wav")
    if os.path.exists(path_hit):
        SND_PERFECT = pygame.mixer.Sound(path_hit); SND_GOOD = pygame.mixer.Sound(path_hit)
        SND_GOOD.set_volume(0.5)
    else:
        SND_PERFECT = _synth(880,0.18,"sin",0.005,0.18,0.50); SND_GOOD = _synth(660,0.15,"sin",0.005,0.15,0.40)

    path_fail = resource_path("fail.wav")
    if os.path.exists(path_fail): SND_FAIL = pygame.mixer.Sound(path_fail)
    else: SND_FAIL = _fail_sound()

    path_succ = resource_path("success.wav")
    if os.path.exists(path_succ): SND_SUCCESS = pygame.mixer.Sound(path_succ)
    else: SND_SUCCESS = _success()

    SND_THUMP = _thump(); SND_ALARM = _alarm(); SND_CHARGE = _synth(220,0.08,"sq", 0.002,0.08,0.15)
    SND_HOVER = _hover_sound(); SND_CLICK = _click_sound()
    SOUND_OK = True
except Exception as e: print(f"Sound init error: {e}")

def play(snd):
    if SOUND_OK and snd is not None:
        try: snd.play()
        except Exception: pass

# ── Game Data ─────────────────────────────────────────────────────────────────
OBSTACLES = [
    {"id":"candy", "name":"硬糖果",   "max_progress":12, "color":(6,182,212)},
    {"id":"meat",  "name":"大塊牛排", "max_progress":21, "color":(245,158,11)},
    {"id":"mochi", "name":"黏性麻糬", "max_progress":30, "color":(217,70,239)},
]
PATIENT_TYPES = ["standard","standard","pregnant","obese"]
MAX_POPUPS = 12  # 【防護】Popup 上限，防止連擊下無限疊加
# 【⑦ 難度系統】各難度的氧氣消耗速率與節鮏速度係數
DIFFICULTY_SETTINGS = {
    "easy":   {"o2_rate": 0.8,  "beat_mult": 0.7,  "label": "輕鬆"},
    "normal": {"o2_rate": 1.5,  "beat_mult": 1.0,  "label": "標準"},
    "hard":   {"o2_rate": 2.8,  "beat_mult": 1.4,  "label": "急迫★"},
}
BX, BY, BW, BH = 570, 160, 390, 500

# ── Optimized Draw Utils ──────────────────────────────────────────────────────
_RRECT_CACHE = {}

def rrect(surf, col, rect, r, bw=0, bc=None, alpha=255):
    if alpha < 255:
        key = (rect[2], rect[3], col, r, alpha)
        if key not in _RRECT_CACHE:
            s = pygame.Surface((rect[2], rect[3]), pygame.SRCALPHA)
            pygame.draw.rect(s, (*col, alpha), (0, 0, rect[2], rect[3]), border_radius=r)
            _RRECT_CACHE[key] = s
        surf.blit(_RRECT_CACHE[key], (rect[0], rect[1]))
    else:
        pygame.draw.rect(surf, col, rect, border_radius=r)
    if bw and bc:
        pygame.draw.rect(surf, bc, rect, bw, border_radius=r)
    # 【優化】漸進淘汰舊項目，避免全清導致的 cache avalanche
    if len(_RRECT_CACHE) > 800:
        for _k in list(_RRECT_CACHE.keys())[:400]: del _RRECT_CACHE[_k]

def draw_icon(surf, type, x, y, size, col):
    """繪製向量圖示，取代易發出亂碼的 Emoji"""
    s = LogicalScreen.s(size); h = s // 2
    if type == "trophy":
        pygame.draw.rect(surf, col, (x - h, y - h, s, s // 2), border_radius=s // 6)
        pygame.draw.circle(surf, col, (x, y), h // 2)
        pygame.draw.line(surf, col, (x, y), (x, y + h), 2)
        pygame.draw.line(surf, col, (x - h, y + h), (x + h, y + h), 3)
    elif type == "clock":
        pygame.draw.circle(surf, col, (x, y), h, 2)
        pygame.draw.line(surf, col, (x, y), (x, y - h + 4), 2)
        pygame.draw.line(surf, col, (x, y), (x + h - 6, y), 2)
    elif type == "target":
        pygame.draw.circle(surf, col, (x, y), h, 2)
        pygame.draw.circle(surf, col, (x, y), h // 3, 2)
        pygame.draw.line(surf, col, (x - h, y), (x + h, y), 1)
        pygame.draw.line(surf, col, (x, y - h), (x, y + h), 1)
    elif type == "fire":
        pts = [(x, y - h), (x + h // 2, y), (x, y + h), (x - h // 2, y)]
        pygame.draw.polygon(surf, col, pts)
    elif type == "alert":
        pygame.draw.polygon(surf, col, [(x, y - h), (x + h, y + h), (x - h, y + h)])
        pygame.draw.line(surf, C["white"], (x, y - h + 6), (x, y + h - 10), 2)
        pygame.draw.circle(surf, C["white"], (x, y + h - 4), 2)

_GLOW_CACHE = {}

def glow(surf, col, cx, cy, r, steps=4, a0=55):
    key = (col, r, steps, a0)
    if key not in _GLOW_CACHE:
        mr = r + steps * 6
        gs = pygame.Surface((mr * 2, mr * 2), pygame.SRCALPHA)
        for i in range(steps, 0, -1):
            rr = r + i * 6; alpha = a0 // i
            pygame.draw.circle(gs, (*col, alpha), (mr, mr), rr)
        _GLOW_CACHE[key] = (gs, mr)
    
    gs, mr = _GLOW_CACHE[key]
    surf.blit(gs, (cx - mr, cy - mr))
    # 【優化】漸進淘汰，保留一半熱資料
    if len(_GLOW_CACHE) > 160:
        for _k in list(_GLOW_CACHE.keys())[:80]: del _GLOW_CACHE[_k]

def lerp(a, b, t): return a + (b - a) * t
def pulse_col(col, amt=40):
    f = 0.5 + 0.5 * math.sin(pygame.time.get_ticks() * 0.008)
    return tuple(min(255, max(0, c + int(f * amt))) for c in col)

# ── 【效能優化】Sprite 架構粒子系統 ──────────────────────────────────────────
class Particle(pygame.sprite.Sprite):
    """繼承自 Sprite，使用 C 語言底層加速群組渲染與 Alpha 預渲染快取"""
    _alpha_cache = {}

    def __init__(self, x, y, col, speed=220, gravity=300, size=5, life=0.55):
        super().__init__()
        angle = random.uniform(0, math.tau); spd = random.uniform(speed * 0.4, speed)
        self.x, self.y = float(x), float(y)
        self.vx, self.vy = math.cos(angle) * spd, math.sin(angle) * spd
        self.col = col; self.size = random.randint(3, 6)
        self.life = life; self.max_life = life; self.gravity = gravity
        self._generate_cache()
        
        self.image = Particle._alpha_cache[(self.col, self.size)][10]
        self.rect = self.image.get_rect(center=(int(self.x), int(self.y)))

    def _generate_cache(self):
        key = (self.col, self.size)
        if key not in Particle._alpha_cache:
            steps = []
            for a in range(11):
                s = pygame.Surface((self.size*2, self.size*2), pygame.SRCALPHA)
                pygame.draw.circle(s, (*self.col, int(a*25.5)), (self.size, self.size), self.size)
                steps.append(s)
            Particle._alpha_cache[key] = steps

    def update(self, dt):
        self.x += self.vx * dt; self.y += self.vy * dt
        self.vy += self.gravity * dt; self.life -= dt

        if self.life <= 0:
            self.kill() # 自動脫離 Group，完美釋放記憶體
        else:
            t = self.life / self.max_life
            alpha_idx = max(0, min(10, int(t * 10)))
            self.image = Particle._alpha_cache[(self.col, self.size)][alpha_idx]
            self.rect.center = (int(self.x), int(self.y))

def burst(group, x, y, col, count=18, **kw):
    for _ in range(count):
        group.add(Particle(x, y, col, **kw))

class Popup:
    __slots__ = ("text", "col", "x", "y", "vy", "life", "max_life", "font", "_surf")
    def __init__(self, text, x, y, col, font=None, life=1.0, vy=-90):
        self.text = text; self.col = col; self.x, self.y = float(x), float(y)
        self.vy = float(vy); self.life = life; self.max_life = life
        self.font = font or F22
        self._surf = get_text_surf(text, self.font, col)

    def update(self, dt):
        self.y += self.vy * dt; self.vy += 60 * dt; self.life -= dt

    def draw(self, surf):
        t = self.life / self.max_life; alpha = int(255 * min(t * 3, 1.0))
        self._surf.set_alpha(alpha)
        surf.blit(self._surf, self._surf.get_rect(center=(int(self.x), int(self.y))))

# ── Beat Bar ──────────────────────────────────────────────────────────────────
class BeatBar:
    BAR_W=300; BAR_H=32; PERIOD=1.4
    def __init__(self):
        self.phase=0.0; self.speed=1.0/self.PERIOD; self.direction=1
    def reset(self, obstacle_id, beat_mult=1.0):
        speeds = {"candy": 0.68, "meat": 0.90, "mochi": 1.15}
        self.speed = speeds.get(obstacle_id, 0.80) * beat_mult  # 【⑦】難度係數調節速度
        self.phase = random.uniform(0.0, 1.0); self.direction = random.choice([-1, 1])
    def update(self,dt):
        self.phase+=self.speed*self.direction*dt
        if self.phase>=1.0: self.phase=1.0; self.direction=-1
        elif self.phase<=0.0: self.phase=0.0; self.direction=1
    def rate(self):
        p=self.phase
        if 0.38<=p<=0.62: return "perfect"
        if 0.22<=p<=0.78: return "good"
        return "miss"

# ── Game State ────────────────────────────────────────────────────────────────
class Game:
    def __init__(self):
        self.state="start"; self.t=0.0
        self.particle_group = pygame.sprite.Group()
        self.popups=[]
        self.beat_bar=BeatBar()
        self.shake_x=self.shake_y=0; self.shake_t=0.0; self.shake_str=0
        self.fail_flash=0.0; self.hit_flash=0.0
        self.trans_t=0.0; self.trans_dir=0
        self._alarm_t=0.0
        self.obstacle=OBSTACLES[0]; self.patient_type="standard"
        self.difficulty  = "normal"  # 【⑦】難度，起始畫選擇後跨局保留
        self.o2_rate     = 1.5       # 【⑦】動態汱氣消耗
        self.beat_mult   = 1.0       # 【⑦ 】難度係數，_finish_trans 也需要它
        self.miss_reasons = {"timing": 0, "power": 0, "abort": 0}
        self._reset_vars()

    def _reset_vars(self):
        self.stage="back"; self.phase="locate"
        self.oxygen=100.0; self.global_progress=0.0
        self.slap_count=0; self.thrust_count=0
        self.is_charging=False; self.power=0.0; self.last_hovered_btn=None
        self.is_spot_found=False; self.target_y=60.0; self.cursor_y_px=None
        self.combo=0; self.max_combo=0
        self.total_hits=0; self.perfect_hits=0; self.good_hits=0; self.miss_count=0
        self.elapsed=0.0; self._start_ms=0
        self.message="移動滑鼠尋找：兩肩胛骨之間"
        self.miss_reasons = {"timing": 0, "power": 0, "abort": 0}  # 【⑧】重置失誤原因統計

    def start_game(self, p_type=None):
        self._reset_vars()
        self.patient_type = p_type or random.choice(PATIENT_TYPES)
        self.target_y = 60.0
        self.obstacle=random.choice(OBSTACLES).copy()
        self.obstacle["max_progress"] = random.randint(20, 30)
        self.state="playing"; self.t=0.0
        self.fail_flash=0.0; self.hit_flash=0.0
        self.particle_group.empty(); self.popups.clear()
        self.trans_t=0.0; self._alarm_t=0.0
        self._start_ms=pygame.time.get_ticks()
        # 【⑦】管用難度設定
        _d = DIFFICULTY_SETTINGS.get(self.difficulty, DIFFICULTY_SETTINGS["normal"])
        self.o2_rate   = _d["o2_rate"]
        self.beat_mult = _d["beat_mult"]
        self.beat_bar.reset(self.obstacle["id"], beat_mult=self.beat_mult)

    def _shake(self,strength=8,dur=0.18):
        self.shake_str=strength; self.shake_t=dur
    def _update_shake(self,dt):
        if self.shake_t>0:
            self.shake_t-=dt
            mag=max(0, self.shake_str*(self.shake_t/0.18))
            self.shake_x=random.randint(-int(mag),int(mag))
            self.shake_y=random.randint(-int(mag)//2,int(mag)//2)
        else: self.shake_x=self.shake_y=0

    def _body_cx_cy(self): return BX, BY+int(self.target_y/100*BH)
    def _popup(self, text, x, y, col, font=None, life=1.0):
        if len(self.popups) < MAX_POPUPS:  # 【③ 防護】避免 popup 無限疊加
            self.popups.append(Popup(text, x, y, col, font, life))

    def trigger_back_slap(self):
        rate=self.beat_bar.rate(); self.total_hits+=1
        cx,cy=self._body_cx_cy()
        if rate=="perfect":
            pg=2; self.combo+=1; self.perfect_hits+=1
            col=C["emerald"]; msg="+2  PERFECT!"
            play(SND_PERFECT); self._shake(12,0.20); self.hit_flash=0.15
            burst(self.particle_group,cx,cy,col,count=20,speed=200,gravity=270)
        elif rate=="good":
            pg=1; self.combo+=1; self.good_hits+=1
            col=C["amber"]; msg="+1  GOOD"
            play(SND_GOOD); self._shake(6,0.13); self.hit_flash=0.08
            burst(self.particle_group,cx,cy,col,count=10,speed=130,gravity=250)
        else:
            pg=0; self.combo=0; self.miss_count+=1
            self.miss_reasons["timing"] += 1  # 【⑧】記錄時機失誤
            col=C["red"]; msg="MISS!"
            play(SND_FAIL); self.oxygen=max(0,self.oxygen-5); self.fail_flash=0.35
            burst(self.particle_group,cx,cy,col,count=8,speed=100,gravity=300)

        if self.combo>self.max_combo: self.max_combo=self.combo
        self._popup(msg,cx,cy-35,col,F28 if rate=="perfect" else F22,life=0.9)
        if self.combo>=3: self._popup(f"COMBO ×{self.combo}!",cx+70,cy-75,C["gold"],F22,life=0.85)

        if pg==0: return
        self.slap_count+=1; self.global_progress+=pg
        if self.global_progress>=self.obstacle["max_progress"]: self._win(); return
        if self.slap_count>=5: self._start_trans("front")
        else: self.message=f"用力拍打！（本輪 {self.slap_count} / 5）"

    def trigger_thrust_success(self):
        self.thrust_count+=1; self.global_progress+=1
        self.total_hits+=1; self.perfect_hits+=1; self.combo+=1
        if self.combo>self.max_combo: self.max_combo=self.combo
        self.is_charging=False; self.power=0.0
        play(SND_PERFECT); self._shake(14,0.22); self.hit_flash=0.18
        cx,cy=self._body_cx_cy()
        burst(self.particle_group,cx,cy,C["emerald"],count=22,speed=200,gravity=250)
        burst(self.particle_group,cx,cy,C["cyan"],count=10,speed=140,gravity=200)
        self._popup("完美衝擊！",cx,cy-40,C["emerald"],F28,life=1.0)
        if self.combo>=3: self._popup(f"COMBO ×{self.combo}!",cx+65,cy-80,C["gold"],F22,0.85)
        if self.global_progress>=self.obstacle["max_progress"]: self._win(); return
        if self.thrust_count>=5: self._start_trans("back")
        else:
            self.phase="locate"
            base=65.0 if self.patient_type in("pregnant","obese") else 92.0
            self.target_y=base+random.uniform(-4,4)
            lb="兩乳頭連線中點" if self.patient_type in("pregnant","obese") else "肚臍上方兩指幅"
            self.message=f"異物鬆動！再次鎖定{lb}施力點"

    def trigger_fail(self, reason):
        self.is_charging=False; self.power=0.0; self.combo=0
        self.miss_count+=1; self.total_hits+=1; self.oxygen=max(0,self.oxygen-8)
        # 【⑧】依原因分類記錄失誤
        if "力道" in reason or "過猛" in reason: self.miss_reasons["power"] += 1
        elif "中斷" in reason:                        self.miss_reasons["abort"] += 1
        else:                                           self.miss_reasons["timing"] += 1
        self.phase="locate"; self.message=f"失敗：{reason}"
        self.fail_flash=0.45; play(SND_FAIL); self._shake(10,0.22)
        cx,cy=self._body_cx_cy()
        burst(self.particle_group,cx,cy,C["red"],count=14,speed=130,gravity=300)
        self._popup("FAIL!",cx,cy-30,C["red"],F28,life=0.85)

    def _start_trans(self,to):
        self.phase="transition"; self.trans_t=0.55; self.trans_dir=1 if to=="front" else -1
        self.message=f"切換至{'正面' if to=='front' else '背面'}！" + (f"{self.obstacle['name']} 頑強抵抗" if to=="front" else "繼續拍背！")

    def _finish_trans(self):
        if self.trans_dir==1:
            self.stage="front"; self.phase="locate"; self.thrust_count=0
            self.target_y=65.0 if self.patient_type in("pregnant","obese") else 92.0
            lb="兩乳頭連線中點" if self.patient_type in("pregnant","obese") else "肚臍上方兩指幅"
            self.message=f"鎖定{lb}施力點！"
        else:
            self.stage="back"; self.phase="locate"; self.slap_count=0
            # 統一背面基準點為 60.0
            self.target_y = 60.0
            self.message="鎖定兩肩胛骨之間，繼續拍背！"
        self.beat_bar.reset(self.obstacle["id"], beat_mult=self.beat_mult)

    def _win(self):
        self.state="victory"
        self.elapsed=(pygame.time.get_ticks()-self._start_ms)/1000.0
        play(SND_SUCCESS)
        cx,cy=BX,BY+BH//2
        for col in[C["emerald"],C["gold"],C["cyan"],C["fuchsia"]]:
            burst(self.particle_group,cx,cy,col,count=25,speed=260,gravity=200)

    def update(self, dt, mx, my):
        self.t += dt
        self.particle_group.update(dt)  # 批次更新
        # 【③ 優化】in-place 刪除死亡 popup，避免每幀建立新 list
        i = 0
        while i < len(self.popups):
            self.popups[i].update(dt)
            if self.popups[i].life <= 0: self.popups.pop(i)
            else: i += 1
        self.fail_flash=max(0,self.fail_flash-dt); self.hit_flash=max(0,self.hit_flash-dt)
        self._update_shake(dt)

        if self.state!="playing": return

        self.oxygen -= self.o2_rate * dt  # 【⑦】消耗速率依難度調整
        if self.oxygen<=0:
            self.oxygen=0; self.state="gameover"
            self.elapsed=(pygame.time.get_ticks()-self._start_ms)/1000.0
            play(SND_ALARM); return

        if self.oxygen<25:
            self._alarm_t+=dt
            if self._alarm_t>1.2: self._alarm_t=0; play(SND_ALARM)

        self.beat_bar.update(dt)

        if self.is_charging and self.phase=="inward" and self.stage=="front":
            self.power+=3.0*(dt/0.03)
            if self.power>100: self.power=0.0; self.trigger_fail("用力過猛！"); return

        if self.phase=="transition":
            self.trans_t-=dt
            if self.trans_t<=0: self._finish_trans()
            return

        if self.phase=="locate":
            bx0=BX-BW//2
            if bx0<=mx<=bx0+BW and BY<=my<=BY+BH:
                self.cursor_y_px=my; y_pct=(my-BY)/BH*100
                tol = 8 if self.stage == "back" else 5
                if abs(y_pct-self.target_y)<tol:
                    self.is_spot_found=True
                else:
                    self.is_spot_found=False
                    lb=("兩肩胛骨之間" if self.stage=="back" else("兩乳頭連線中點" if self.patient_type!="standard" else "肚臍上方兩指幅"))
                    self.message=f"移動滑鼠尋找：{lb}"
            else: self.cursor_y_px=None; self.is_spot_found=False

    def on_mouse_down(self,button):
        if self.state!="playing" or button!=1 or self.phase=="transition": return
        if self.phase=="locate" and self.is_spot_found:
            if self.stage=="back": self.phase="slap"; self.message="跟著節奏，在 PERFECT 區點擊！"
            else: self.phase="inward"; self.is_charging=True; self.message="長按蓄力，進入 PERFECT 區後按 W！"
            return
        if self.stage=="back" and self.phase=="slap": self.trigger_back_slap()
        elif self.stage=="front" and self.phase=="inward" and not self.is_charging:
            self.is_charging=True; play(SND_CHARGE)

    def on_mouse_up(self,button):
        if button!=1: return
        if self.is_charging and self.stage=="front" and self.state=="playing":
            self.is_charging=False
            if self.phase=="inward": self.trigger_fail("動作中斷！必須一氣呵成")

    def on_key_down(self,key):
        if self.state!="playing": return
        if key==pygame.K_w:
            if self.stage=="front" and self.phase=="inward" and self.is_charging:
                if 70<=self.power<=90: self.trigger_thrust_success()
                else: self.trigger_fail("力道不足！" if self.power<70 else "用力過猛！")

    def rating(self):
        if self.total_hits == 0: return "F"
        acc = self.perfect_hits / self.total_hits
        if acc >= 0.80 and self.elapsed < 45: return "S"
        if acc >= 0.65: return "A"
        if acc >= 0.45: return "B"
        if acc >= 0.25: return "C"
        return "F"

    def get_score(self):
        if self.total_hits == 0: return 0
        acc = self.perfect_hits / self.total_hits
        time_bonus = max(0, (60 - self.elapsed) * 0.5) if self.state == "victory" else 0
        return int((acc * 70) + min(30, time_bonus))

# ── Simulation Renderer ───────────────────────────────────────────────────────
class SimulationRenderer:
    _BG_CACHE       = None
    _MAIN_BG        = None
    _SCALED_BG      = None
    _FRONT_IMG      = None
    _BACK_IMG       = None
    _SCALED_FRONT   = None
    _SCALED_BACK    = None
    _LAST_SIZE      = (0, 0)
    _FAIL_OVERLAY   = None  # 【快取】失敗閃爍全螢幕遮罩 Surface
    _HIT_FLASH_SURF = None  # 【快取】擊中閃爍面板 Surface
    _DIM_SURF       = None  # 【② 快取】勝負畫面半透明遮罩 Surface
    _JET_SURF       = None  # 【② 快取】蓄力氣流 Surface

    @staticmethod
    def _load_bg():
        """載入大背景圖與人體剖面圖，使用 try-except 與資源防護"""
        if SimulationRenderer._FRONT_IMG is not None: return
        try:
            p_front = resource_path("正面.jpg")
            p_back = resource_path("背面.jpg")
            p_bg = resource_path("restaurant_bg.png")
            p_illus = resource_path("heimlich_simulator.png")
            # 詳加確認檔案存在
            if os.path.exists(p_front): SimulationRenderer._FRONT_IMG = pygame.image.load(p_front).convert()
            if os.path.exists(p_back): SimulationRenderer._BACK_IMG = pygame.image.load(p_back).convert()
            if os.path.exists(p_bg): SimulationRenderer._MAIN_BG = pygame.image.load(p_bg).convert()
            
            if os.path.exists(p_illus):
                img = pygame.image.load(p_illus).convert_alpha()
                iw, ih = img.get_size()
                sc = 760 / iw # 寬度提升至 760
                SimulationRenderer._ILLUS_IMG = pygame.transform.smoothscale(img, (760, int(ih * sc)))
            else: SimulationRenderer._ILLUS_IMG = False
        except Exception as e:
            print(f"資源載入失敗: {e}")
            SimulationRenderer._FRONT_IMG = None
            SimulationRenderer._BACK_IMG = None
            SimulationRenderer._ILLUS_IMG = None

    @staticmethod
    def draw_background(surf, g):
        w, h = surf.get_size()
        if h <= 0: return
        SimulationRenderer._load_bg()
        
        # 背景快取邏輯：視窗縮放或狀態切換 (操作頁面 vs 其他) 時重刷
        is_playing = (g.state == "playing")
        cache_key = (w, h, is_playing)
        if getattr(SimulationRenderer, "_LAST_BG_KEY", None) != cache_key:
            bg = pygame.Surface((w, h))
            if is_playing and SimulationRenderer._MAIN_BG:
                # 只有在操作頁面才顯示像素背景
                iw, ih = SimulationRenderer._MAIN_BG.get_size()
                scale = max(w / iw, h / ih)
                nw, nh = max(1, int(iw * scale)), max(1, int(ih * scale)) # 防禦 0 像素崩潰
                tmp = pygame.transform.smoothscale(SimulationRenderer._MAIN_BG, (nw, nh))
                bg.blit(tmp, ((w - nw) // 2, (h - nh) // 2))
                dark = pygame.Surface((w, h), pygame.SRCALPHA)
                dark.fill((10, 15, 30, 145))
                bg.blit(dark, (0, 0))
            else:
                # 其他頁面回歸深藍漸層與網格
                for i in range(0, h, 4):
                    f = i / h
                    c = (int(lerp(4, 13, f)), int(lerp(9, 21, f)), int(lerp(22, 40, f)))
                    pygame.draw.line(bg, c, (0, i), (w, i), 4)
                for x in range(0, BASE_W + 60, 60): 
                    px, _ = LogicalScreen.to_screen(x, 0)
                    pygame.draw.line(bg, (18, 26, 42), (px, 0), (px, h))
                for y in range(0, BASE_H + 60, 60): 
                    _, py = LogicalScreen.to_screen(0, y)
                    pygame.draw.line(bg, (18, 26, 42), (0, py), (w, py))
            SimulationRenderer._SCALED_BG = bg
            SimulationRenderer._LAST_BG_KEY = cache_key
            
        surf.blit(SimulationRenderer._SCALED_BG, (0, 0))

    @staticmethod
    def draw_body_panel(surf, g):
        bx_s, by_s = LogicalScreen.to_screen(BX - BW//2, BY)
        bw_s, bh_s = LogicalScreen.s(BW), LogicalScreen.s(BH)
        bc = C["orange"] if g.stage == "back" else C["cyan"]
        sx, sy = LogicalScreen.s(g.shake_x), LogicalScreen.s(g.shake_y)
        hx = BW // 2
        
        # 繪製面板邊框與背景
        rrect(surf, C["panel"], (bx_s + sx, by_s + sy, bw_s, bh_s), LogicalScreen.s(24), 2, bc, 220)

        # 【效能優化 v5.0】分解渲染：靜態底層 (Cached) vs 動態疊層 (Direct Draw)
        if not hasattr(SimulationRenderer, "_STATIC_BODY_SURF"):
            SimulationRenderer._STATIC_BODY_SURF = pygame.Surface((BW, BH), pygame.SRCALPHA)
        
        # 判定是否需要重刷靜態底層 (僅在切換階段或模式時執行)
        sc_id = (g.stage, g.patient_type)
        if getattr(SimulationRenderer, "_LAST_STATIC_ID", None) != sc_id:
            static_body = SimulationRenderer._STATIC_BODY_SURF; static_body.fill((0, 0, 0, 0))
            # 1. 解剖圖
            SimulationRenderer._load_bg()
            target_img = SimulationRenderer._BACK_IMG if g.stage == "back" else SimulationRenderer._FRONT_IMG
            if target_img:
                iw, ih = target_img.get_size()
                sc = max(BW / iw, BH / ih)
                nw, nh = max(1, int(iw * sc)), max(1, int(ih * sc))
                scaled = pygame.transform.smoothscale(target_img, (nw, nh))
                off_y = -30 if g.stage=="front" else 0 
                static_body.blit(scaled, ((BW-nw)//2, off_y))

            # 2. 標籤
            vl = "背面 (Dorsal)" if g.stage == "back" else "正面 (Ventral)"
            vc = C["orange"] if g.stage == "back" else C["cyan"]
            vw, vh2 = F13.size(vl); vw += 20
            rrect(static_body, (*vc, 190), (hx - vw // 2, 8, vw, vh2 + 6), 10); tc(static_body, vl, F13, C["white"], hx, 8 + (vh2+6)//2)

            pl = f"模式：{'一般' if g.patient_type=='standard' else ('孕婦' if g.patient_type=='pregnant' else '肥胖')}"
            pc = C["emerald"] if g.patient_type == "standard" else C["pink"]
            pw, ph2 = F13.size(pl); pw += 16
            rrect(static_body, (*pc, 170), (hx - pw // 2, 16+vh2, pw, ph2 + 6), 9); tc(static_body, pl, F13, C["white"], hx, 16+vh2 + (ph2+6)//2)

            # 3. 氣管與內部幾何
            aw, ah, ax, ay = 45, 180, hx - 22, 120
            rrect(static_body, (*C["s950"], 210), (ax, ay, aw, ah), 15, 1, (*C["cyan"], 100))
            for i in range(10): pygame.draw.line(static_body, (*C["cyan"], 40), (ax + 6, ay + 12 + i * 16), (ax + aw - 6, ay + 12 + i * 16), 1)
            pygame.draw.arc(static_body, (*C["cyan"], 60), (hx - 22, 105, 45, 45), 0, 1.57, 2)
            
            SimulationRenderer._LAST_STATIC_ID = sc_id
            SimulationRenderer._SCALED_BODY_CACHE = None # 標記需要重新縮放底層
        
        # 進行單次高規縮放 (僅在視窗解析度改變時重算)
        if SimulationRenderer._SCALED_BODY_CACHE is None or getattr(SimulationRenderer, "_LAST_BODY_SIZE", None) != (bw_s, bh_s):
            SimulationRenderer._SCALED_BODY_CACHE = pygame.transform.smoothscale(SimulationRenderer._STATIC_BODY_SURF, (bw_s, bh_s))
            SimulationRenderer._LAST_BODY_SIZE = (bw_s, bh_s)
        
        # 繪製靜態層至螢幕 (並主動加上碰撞震動偏移)
        surf.blit(SimulationRenderer._SCALED_BODY_CACHE, (bx_s + sx, by_s + sy))

        # 【動態層渲染】
        def to_s(lx, ly): return (bx_s + sx + LogicalScreen.s(lx), by_s + sy + LogicalScreen.s(ly))

        # 4. 異物 (Bead)
        aw, ah, ay = 45, 180, 120
        pr = g.global_progress / g.obstacle["max_progress"]
        bead_y = ay + ah - 10 - int(pr * (ah - 14))
        tremor = int(4 * pr * math.sin(g.t * 18)) if pr > 0.3 else 0
        b_pos = to_s(hx + tremor, bead_y)
        if g.global_progress < g.obstacle["max_progress"]:
            bc2 = g.obstacle["color"]; glow(surf, bc2, b_pos[0], b_pos[1], LogicalScreen.s(7), 3, 60)
            pygame.draw.circle(surf, bc2, b_pos, LogicalScreen.s(7))
            pygame.draw.circle(surf, (255, 255, 255), b_pos, LogicalScreen.s(3))
        else:
            v_p = to_s(hx, ay - 8)
            glow(surf, C["emerald"], v_p[0], v_p[1], LogicalScreen.s(8), 3, 100); 
            pygame.draw.circle(surf, C["emerald"], v_p, LogicalScreen.s(8))

        # 5. 蓄力氣流 (轉為直接畫在 surf 上，並套用邏輯縮放)
        if g.is_charging and g.stage == "front":
            s_bw, s_jet_h = LogicalScreen.s(BW), LogicalScreen.s(60)
            # 【② 優化】重用預建 Surface，避免每幀 new
            if SimulationRenderer._JET_SURF is None or SimulationRenderer._JET_SURF.get_size() != (s_bw, s_jet_h):
                SimulationRenderer._JET_SURF = pygame.Surface((s_bw, s_jet_h), pygame.SRCALPHA)
            SimulationRenderer._JET_SURF.fill((0, 0, 0, 0))  # 清除前一幀
            for step in range(5):
                pygame.draw.rect(SimulationRenderer._JET_SURF, (*C["cyan"], int(60 * (g.power / 100) * (step / 4))), (0, LogicalScreen.s(step * 12), s_bw, LogicalScreen.s(12)))
            surf.blit(SimulationRenderer._JET_SURF, to_s(0, ay + ah - 20))

        # 6. 尋找施力點的游標線 (轉換至螢幕座標)
        if g.cursor_y_px and g.phase == "locate":
            lcy = g.cursor_y_px - BY
            if 0 <= lcy <= BH:
                sc = C["emerald"] if g.is_spot_found else C["red"]
                left_x, s_y = to_s(0, lcy)
                right_x = left_x + bw_s
                th, tw = LogicalScreen.s(6), LogicalScreen.s(10)
                
                pygame.draw.line(surf, sc, (left_x, s_y), (right_x, s_y), max(1, LogicalScreen.s(3)))
                pygame.draw.polygon(surf, sc, [(right_x-tw, s_y-th), (right_x, s_y), (right_x-tw, s_y+th)])
                pygame.draw.polygon(surf, sc, [(left_x+tw, s_y-th), (left_x, s_y), (left_x+tw, s_y+th)])

        # 7. 施力點目標光圈 (轉換至螢幕座標)
        if g.phase not in ("locate", "transition"):
            ty = int(g.target_y / 100 * BH); rx2, ry2 = hx, ty
            rc = C["orange"] if g.stage == "back" else C["emerald"]
            s_rx, s_ry = to_s(rx2, ry2) # 轉換圓心座標
            rad = LogicalScreen.s(35)
            
            for seg in range(4):
                a1 = math.radians((g.t * 120) % 360 + seg * 90)
                pygame.draw.circle(surf, rc, (int(s_rx + rad * math.cos(a1)), int(s_ry + rad * math.sin(a1))), LogicalScreen.s(4))
            glow(surf, rc, s_rx, s_ry, LogicalScreen.s(10), 2, 80)
            pygame.draw.circle(surf, (255, 255, 255), (s_rx, s_ry), LogicalScreen.s(6))

        # 8. 擊中閃爍特效 (直接在目標區域疊加 Alpha 面板)
        if g.hit_flash > 0:
            # 【優化】重用預建 Surface，避免每幀記憶體分配
            if SimulationRenderer._HIT_FLASH_SURF is None or SimulationRenderer._HIT_FLASH_SURF.get_size() != (bw_s, bh_s):
                SimulationRenderer._HIT_FLASH_SURF = pygame.Surface((bw_s, bh_s), pygame.SRCALPHA)
            SimulationRenderer._HIT_FLASH_SURF.fill((*C["emerald"], int(g.hit_flash / 0.18 * 40)))
            surf.blit(SimulationRenderer._HIT_FLASH_SURF, (bx_s + sx, by_s + sy), special_flags=pygame.BLEND_RGBA_ADD)

    @staticmethod
    def draw_hud(surf, g):
        hud_h = LogicalScreen.s(135) # 高度大幅提升
        # 頂部導航欄背景：玻璃擬態
        rrect(surf, (10, 18, 38), (0, 0, surf.get_width(), hud_h), 0, alpha=250)
        pygame.draw.line(surf, (45, 55, 75), (0, hud_h), (surf.get_width(), hud_h), 2)
        
        # 氧氣條：極大化
        o2_w, o2_h = LogicalScreen.s(450), LogicalScreen.s(18)
        o2_x, o2_y = (surf.get_width() // 2 - o2_w // 2, LogicalScreen.s(85))
        rrect(surf, C["s900"], (o2_x, o2_y, o2_w, o2_h), LogicalScreen.s(9), 1, C["s700"])
        fw = int(max(0, g.oxygen) / 100 * (o2_w - 2))
        if fw > 0: 
            o2_col = C["red"] if g.oxygen <= 25 else (C["amber"] if g.oxygen <= 50 else C["emerald"])
            rrect(surf, o2_col, (o2_x + 1, o2_y + 1, fw, o2_h - 2), LogicalScreen.s(8))
        
        tc(surf, f"生命體徵 - 剩餘氧氣 {int(g.oxygen)}%", F18, C["white"], o2_x + o2_w // 2, o2_y - LogicalScreen.s(25), use_cache=False)

        # 標題 (左側)
        tl(surf, "哈姆立克模擬器 v4.3", F22, C["cyan"], LogicalScreen.s(30), LogicalScreen.s(30))
        # 狀態 (右側)
        score_str = f"SCORE: {g.get_score()}"
        tw_s, _ = F22.size(score_str)
        tl(surf, score_str, F22, C["gold"], surf.get_width() - tw_s - LogicalScreen.s(30), LogicalScreen.s(30), use_cache=False)

    @staticmethod
    def draw_overlays(surf, g, mx, my):
        # 【效能優化】直接呼叫 Sprite Group 進行批次渲染
        g.particle_group.draw(surf)
        for p in g.popups: p.draw(surf)
        
        if g.fail_flash > 0:
            # 【優化】重用預建 Surface，避免每幀記憶體分配
            if SimulationRenderer._FAIL_OVERLAY is None or SimulationRenderer._FAIL_OVERLAY.get_size() != surf.get_size():
                SimulationRenderer._FAIL_OVERLAY = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
            SimulationRenderer._FAIL_OVERLAY.fill((*C["red"], int(g.fail_flash / 0.45 * 80)))
            surf.blit(SimulationRenderer._FAIL_OVERLAY, (0, 0))

        if g.state in ("victory", "gameover"):
            # 【② 優化】重用 dim 遮罩，size 不變就不重建
            if SimulationRenderer._DIM_SURF is None or SimulationRenderer._DIM_SURF.get_size() != surf.get_size():
                SimulationRenderer._DIM_SURF = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
                SimulationRenderer._DIM_SURF.fill((4, 9, 22, 220))
            surf.blit(SimulationRenderer._DIM_SURF, (0, 0))  # 加深背景

            bw, bh = LogicalScreen.s(680), LogicalScreen.s(480)
            bx, by = (surf.get_width() // 2 - bw // 2, surf.get_height() // 2 - bh // 2)
            # 強化玻璃擬態 - 雙層邊框與陰影
            rrect(surf, (10, 15, 35), (bx + 8, by + 8, bw, bh), LogicalScreen.s(32), alpha=100) # 陰影
            rrect(surf, C["panel"], (bx, by, bw, bh), LogicalScreen.s(32), 2, C["s600"], 235)
            
            tcol = C["emerald"] if g.state == "victory" else C["red"]
            tc(surf, "急救成功！" if g.state == "victory" else "急救失敗", F48, tcol, surf.get_width() // 2, by + LogicalScreen.s(70))
            
            tc(surf, f"成功排除「{g.obstacle['name']}」！" if g.state == "victory" else g.message, F22, C["text"], surf.get_width() // 2, by + LogicalScreen.s(130))

            stats = [("clock", "耗時", f"{g.elapsed:.1f} 秒"), ("target", "準確率", f"{g.perfect_hits/max(1,g.total_hits)*100:.0f}%" if g.total_hits else "—"),
                     ("fire", "最高連擊", f"×{g.max_combo}"), ("target", "總積分", f"{g.get_score()} 分")]
            
            sx0, sy0 = bx + LogicalScreen.s(80), by + LogicalScreen.s(200)
            for i, (icon, lb, val) in enumerate(stats):
                xl, yl = sx0 + (i % 2) * LogicalScreen.s(280), sy0 + (i // 2) * LogicalScreen.s(80)
                draw_icon(surf, icon, xl - LogicalScreen.s(30), yl + LogicalScreen.s(10), 16, C["s500"])
                tl(surf, lb, F18, C["s500"], xl - LogicalScreen.s(15), yl); tl(surf, val, F28, C["text"], xl - LogicalScreen.s(15), yl + LogicalScreen.s(25))

            rc2 = {"S":C["gold"],"A":C["emerald"],"B":C["cyan"],"C":C["amber"],"F":C["red"]}[g.rating()]
            rrect(surf, C["s950"], (bx + bw - LogicalScreen.s(135), by + LogicalScreen.s(200), LogicalScreen.s(100), LogicalScreen.s(100)), LogicalScreen.s(24), 2, rc2)
            tc(surf, g.rating(), load_font(LogicalScreen.s(60), True), rc2, bx + bw - LogicalScreen.s(85), by + LogicalScreen.s(250))
            tc(surf, "評級", F18, C["s500"], bx + bw - LogicalScreen.s(85), by + LogicalScreen.s(315))

            # 【⑧ 錯誤分析回饋】有失誤時顯示改善建議
            if g.miss_count > 0:
                hints = []
                if g.miss_reasons.get("timing", 0): hints.append(f"時機偏差×{g.miss_reasons['timing']} → 維誤條綠區點擊")
                if g.miss_reasons.get("power",  0): hints.append(f"力道不準×{g.miss_reasons['power']}  → 蓄力 70-90% 再按 W")
                if g.miss_reasons.get("abort",  0): hints.append(f"動作中斷×{g.miss_reasons['abort']}  → 持續按住不放")
                if hints:
                    abox_y = by + LogicalScreen.s(328)
                    abox_h = LogicalScreen.s(14 + 26 * min(len(hints), 2))
                    abox_w = bw - LogicalScreen.s(155)
                    rrect(surf, (6, 12, 28), (bx + LogicalScreen.s(40), abox_y, abox_w, abox_h), LogicalScreen.s(10), 1, C["amber"], 185)
                    tc(surf, "[ 改善建議 ]", F13, C["amber"], bx + LogicalScreen.s(40) + abox_w // 2, abox_y + LogicalScreen.s(9))
                    for j, h in enumerate(hints[:2]):
                        tc(surf, h, F13, C["s400"], bx + LogicalScreen.s(40) + abox_w // 2, abox_y + LogicalScreen.s(23 + j * 24))

            bc3 = C["red2"] if g.state=="gameover" else (40, 180, 100)
            is_hover = pygame.Rect(surf.get_width() // 2 - LogicalScreen.s(140), by + bh - LogicalScreen.s(80), LogicalScreen.s(280), LogicalScreen.s(56)).collidepoint(mx, my)
            # 按鈕 Hover 縮放動畫
            bw_btn = LogicalScreen.s(300 if is_hover else 280)
            bh_btn = LogicalScreen.s(62 if is_hover else 56)
            brect = (surf.get_width() // 2 - bw_btn // 2, by + bh - LogicalScreen.s(80) - (bh_btn - LogicalScreen.s(56))//2, bw_btn, bh_btn)
            
            rrect(surf, (pulse_col(bc3, 40) if is_hover else bc3), brect, bh_btn//2, 2, C["white"] if is_hover else C["s400"])
            tc(surf, "重新演練" if g.state=="gameover" else "返回主選單", F28 if is_hover else F22, C["white"], surf.get_width() // 2, brect[1] + bh_btn//2)
            return pygame.Rect(brect)
        return None

    @staticmethod
    def draw_power_bar(surf, g):
        if g.stage != "front": return
        bx, by = LogicalScreen.to_screen(BX + BW // 2 + 50, BY + 60)
        bw, bh = LogicalScreen.s(65), LogicalScreen.s(480)
        rrect(surf, C["s950"], (bx, by, bw, bh), LogicalScreen.s(32), 1, C["s700"])

        pz_y, pz_h = by + bh - int(0.9 * bh), int(0.2 * bh)
        rrect(surf, C["emerald"], (bx, pz_y, bw, pz_h), LogicalScreen.s(12), alpha=60)
        
        fh = int(g.power / 100 * bh)
        if fh > 0: rrect(surf, C["emerald"] if 70 <= g.power <= 90 else (C["red"] if g.power > 90 else C["amber"]), (bx, by + bh - fh, bw, fh), LogicalScreen.s(16))
        
        # 字體極大化：壓迫力標籤
        tc(surf, "壓迫力", F15, C["white"], bx + bw // 2, by - LogicalScreen.s(35))
        tc(surf, f"{int(g.power)}%", F18, C["cyan"], bx + bw // 2, by + bh + LogicalScreen.s(30))

    @staticmethod
    def draw_phase_bar(surf, g):
        steps = [("步驟 1：鎖定位置", "locate"), ("步驟 2：拍背 ×5", "slap")] if g.stage == "back" else [(f"1. 鎖定{'腹' if g.patient_type == 'standard' else '胸'}部", "locate"), ("2. 蓄力壓迫", "inward"), ("3. 向上推擠", "upward")]
        tw_total = sum(F13.size(s[0])[0] + LogicalScreen.s(45) for s in steps) + (len(steps) - 1) * LogicalScreen.s(15)
        # 第一層：步驟導航列 (Y: 85-115)
        sx, ry = surf.get_width() // 2 - tw_total // 2, LogicalScreen.s(92)

        # 第二層：浮動指令消息 (Y: 150-190)
        msg_y = LogicalScreen.s(165)
        msg_col = C["orange"] if g.stage == "back" else C["cyan"]
        if g.is_spot_found: msg_col = pulse_col(msg_col, 55)
        
        # 【優化】改用 3 個離散尺寸循環，確保 lru_cache 有效命中（原生 sin 產生 12+ 種不同 size）
        msg_font = load_font((44, 41, 38)[int(g.t * 4) % 3], True) if g.is_spot_found else F22
        
        mw, mh = msg_font.size(g.message)[0] + 40, 56
        rrect(surf, (4, 9, 22), (surf.get_width() // 2 - mw // 2, msg_y - 28, mw, mh), 28, alpha=160)
        tc(surf, g.message, msg_font, msg_col, surf.get_width() // 2, msg_y, use_cache=False)
        
        for lb2, pid in steps:
            tw = F15.size(lb2)[0] + LogicalScreen.s(40)
            active = (g.phase == pid) or (pid == "upward" and g.phase == "inward")
            ac = {"locate": C["cyan"], "slap": C["amber"], "inward": C["amber"], "upward": C["emerald"]}.get(pid, C["s600"])
            rrect(surf, ac if active else C["s800"], (sx, ry, tw, LogicalScreen.s(28)), LogicalScreen.s(14), 1, ac if active else C["s700"], alpha=230 if active else 140)
            tc(surf, lb2, F15, C["white"] if active else C["s500"], sx + tw // 2, ry + LogicalScreen.s(14))
            sx += tw + LogicalScreen.s(15)

    @staticmethod
    def draw_beat_bar(surf, g):
        if g.stage != "back" or g.phase != "slap": return
        # 底部 UI (Y: 面板底部 + 25px)
        cx, y = LogicalScreen.to_screen(BX, BY + BH + 25)
        tc(surf, "節奏提示：在 PERFECT 區點擊", F15, C["amber"], cx, y + LogicalScreen.s(12))
        
        bw, bh = LogicalScreen.s(400), LogicalScreen.s(36); x0 = cx - bw // 2
        rrect(surf, C["s800"], (x0, y + LogicalScreen.s(35), bw, bh), LogicalScreen.s(18), 1, C["s700"])
        
        rrect(surf, C["amber"], (x0 + int(0.22 * bw), y + LogicalScreen.s(35) + 2, int(0.56 * bw), bh - 4), LogicalScreen.s(14), alpha=40)
        rrect(surf, C["emerald"], (x0 + int(0.38 * bw), y + LogicalScreen.s(35) + 2, int(0.24 * bw), bh - 4), LogicalScreen.s(12), alpha=80)
        pygame.draw.rect(surf, C["white"], (x0 + int(g.beat_bar.phase * bw) - 4, y + LogicalScreen.s(35) - 6, 8, bh + 12), border_radius=4)
        
        for i in range(5):
            px, py = cx - LogicalScreen.s(60) + i * LogicalScreen.s(30), y + LogicalScreen.s(90)
            pygame.draw.circle(surf, C["emerald"] if i < g.slap_count else C["s700"], (px, py), LogicalScreen.s(10))
            pygame.draw.circle(surf, C["white"], (px, py), LogicalScreen.s(10), 1)

    @staticmethod
    def draw_start_screen(surf, real_mx, real_my, t, g):
        SimulationRenderer.draw_background(surf, g)
        SimulationRenderer._load_bg()
        
        # 標題
        title_y = LogicalScreen.s(95) + int(6 * math.sin(t * 2.2))
        tc(surf, "哈姆立克：黃金三分鐘", F48, (2, 6, 15), surf.get_width() // 2 + 4, title_y + 4)
        tc(surf, "哈姆立克：黃金三分鐘", F48, C["white"], surf.get_width() // 2, title_y)
        tc(surf, "專業急救模擬訓練器", F22, C["cyan"], surf.get_width() // 2, title_y + LogicalScreen.s(85))
        
        # 繪製插圖 (Y: 280-450 區間)
        if hasattr(SimulationRenderer, "_ILLUS_IMG") and SimulationRenderer._ILLUS_IMG:
            floating_y = LogicalScreen.s(290) + int(10 * math.sin(t * 1.5))
            rect = SimulationRenderer._ILLUS_IMG.get_rect(center=(surf.get_width() // 2, floating_y))
            surf.blit(SimulationRenderer._ILLUS_IMG, rect)
            # 插圖陰影
            glow(surf, (15, 25, 45), surf.get_width() // 2, floating_y + rect.height // 2, LogicalScreen.s(20), 2, 35)

        # 【⑥ 難度選擇】模式按鈕上移至 Y=500/572，騰出空間放難度列
        btn_configs = [
            ("一般模式", "standard", C["cyan"],    LogicalScreen.s(500)),
            ("肥胖者及孕婦", "pregnant", C["fuchsia"], LogicalScreen.s(572)),
        ]

        btn_rects = {}
        for label, m_type, col, by in btn_configs:
            is_hover = pygame.Rect(surf.get_width() // 2 - LogicalScreen.s(165), by - LogicalScreen.s(33), LogicalScreen.s(330), LogicalScreen.s(65)).collidepoint(real_mx, real_my)
            bw = LogicalScreen.s(350 if is_hover else 320)
            bh = LogicalScreen.s(70 if is_hover else 62)
            brect = pygame.Rect(surf.get_width() // 2 - bw // 2, by - bh // 2, bw, bh)
            rrect(surf, (pulse_col(C["panel2"], 25) if is_hover else C["panel"]), brect, bh // 2, 2, col if is_hover else C["s700"])
            if is_hover: glow(surf, col, surf.get_width() // 2, by, LogicalScreen.s(20), 2, 45)
            tc(surf, label, F22 if is_hover else F18, C["white"], surf.get_width() // 2, by)
            btn_rects[m_type] = brect

        # 【⑥】難度選擇列 — 3 個水平小按鈕，Y=632
        diff_y  = LogicalScreen.s(632)
        d_bw    = LogicalScreen.s(105)
        d_bh    = LogicalScreen.s(36)
        d_gap   = LogicalScreen.s(10)
        d_start = surf.get_width() // 2 - (3 * d_bw + 2 * d_gap) // 2
        tc(surf, "--- 難度選擇 ---", F13, C["s500"], surf.get_width() // 2, diff_y - LogicalScreen.s(16))
        for i, (dk, dcol) in enumerate([("easy", C["emerald"]), ("normal", C["amber"]), ("hard", C["red"])]):
            dx  = d_start + i * (d_bw + d_gap)
            sel = (g.difficulty == dk)
            hov = pygame.Rect(dx, diff_y, d_bw, d_bh).collidepoint(real_mx, real_my)
            rrect(surf, dcol if sel else (C["s700"] if hov else C["s800"]), (dx, diff_y, d_bw, d_bh), d_bh // 2, 2, dcol if (sel or hov) else C["s600"])
            if sel: glow(surf, dcol, dx + d_bw // 2, diff_y + d_bh // 2, LogicalScreen.s(14), 2, 50)
            tc(surf, DIFFICULTY_SETTINGS[dk]["label"], F13, C["white"] if (sel or hov) else C["s400"], dx + d_bw // 2, diff_y + d_bh // 2)
            btn_rects[f"diff_{dk}"] = pygame.Rect(dx, diff_y, d_bw, d_bh)

        # 提示文字
        hint_y = LogicalScreen.s(700)
        rrect(surf, (4, 9, 22), (surf.get_width() // 2 - LogicalScreen.s(220), hint_y - 12, LogicalScreen.s(440), LogicalScreen.s(30)), 15, alpha=150)
        tc(surf, "講師提示：選擇模式與難度後點擊開始訓練", F15, C["s500"], surf.get_width() // 2, hint_y)
        return btn_rects

# ── 注冊快取清除回調 (在 SimulationRenderer 定義後執行) ─────────────────────────
def _invalidate_sim_caches():
    SimulationRenderer._SCALED_BODY_CACHE = None

_CACHE_INVALIDATORS.append(_invalidate_sim_caches)

# ── Main Loop ─────────────────────────────────────────────────────────────────
def main():
    # 載入背景音樂
    try:
        bgm_path = resource_path("Before_The_Stillness.mp3")
        if os.path.exists(bgm_path):
            pygame.mixer.music.load(bgm_path)
            pygame.mixer.music.set_volume(0.7)
            pygame.mixer.music.play(-1)
    except Exception as e: print(f"BGM 載入失敗: {e}")

    g = Game()
    btn_rect = None
    
    while True:
        dt = min(clock.tick(FPS) / 1000.0, 0.05)  # 【① 鉗制】最大步長 50ms，防視窗拖曳時物理暴衝
        real_mx, real_my = pygame.mouse.get_pos()
        mx, my = LogicalScreen.to_world(real_mx, real_my)
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            elif event.type == pygame.VIDEORESIZE:
                LogicalScreen.update(event.w, event.h)
                # 必須重新設定 mode 才能真正改變 Pygame 底層表面大小
                global screen
                screen = pygame.display.set_mode((event.w, event.h), pygame.RESIZABLE)
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if g.state == "start": pygame.quit(); sys.exit()
                    else: g.state = "start" # 從遊戲或結算畫面跳回主選單
                g.on_key_down(event.key)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if g.state == "start":
                    if btn_rect and isinstance(btn_rect, dict):
                        for key, rect in btn_rect.items():
                            if rect.collidepoint(real_mx, real_my):
                                if key.startswith("diff_"):
                                    # 【⑦】點擊難度按鈕 —— 更新難度但不開嚴桃
                                    g.difficulty = key[5:]  # "easy"/"normal"/"hard"
                                else:
                                    if SND_CLICK: SND_CLICK.play()
                                    g.start_game(key)  # "standard" / "pregnant"
                                break
                elif g.state in ("gameover", "victory"):
                    if btn_rect and isinstance(btn_rect, pygame.Rect) and btn_rect.collidepoint(real_mx, real_my): 
                        if g.state == "victory": g.state = "start"
                        else: g.start_game()
                else:
                    g.on_mouse_down(event.button)
            elif event.type == pygame.MOUSEBUTTONUP:
                g.on_mouse_up(event.button)

        g.update(dt, mx, my)

        SimulationRenderer.draw_background(screen, g)

        if g.state == "start":
            # 傳遞真實滑鼠座標以進行螢幕空間之碰撞偵測
            btn_rect = SimulationRenderer.draw_start_screen(screen, real_mx, real_my, g.t, g)
            # 懸停音效邏輯
            current_hover = None
            if btn_rect and isinstance(btn_rect, dict):
                for m_type, rect in btn_rect.items():
                    if rect.collidepoint(real_mx, real_my):
                        current_hover = m_type; break
            if current_hover != g.last_hovered_btn:
                if current_hover is not None and SND_HOVER: 
                    SND_HOVER.play()
                g.last_hovered_btn = current_hover
        else:
            SimulationRenderer.draw_body_panel(screen, g)
            SimulationRenderer.draw_hud(screen, g)
            SimulationRenderer.draw_phase_bar(screen, g)
            SimulationRenderer.draw_power_bar(screen, g)
            SimulationRenderer.draw_beat_bar(screen, g)
            btn_rect = SimulationRenderer.draw_overlays(screen, g, real_mx, real_my)

        pygame.display.flip()

if __name__=="__main__":
    main()