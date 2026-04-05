"""
哈姆立克：黃金三分鐘  v4.3 (Web Integrated Version)
─────────────────────────────────────────────────
優化核心：
  1. 模組化整合：改裝為 run_heimlich(screen, clock) 供主程式呼叫。
  2. 非同步支援：加入 asyncio.sleep(0) 以相容 Pygbag Web 環境。
  3. 資源路徑優化：確保在 Web 下資源載入路徑正確。
"""

import pygame, sys, random, math, array, functools, os, asyncio

# ── Configuration ─────────────────────────────────────────────────────────────
BASE_W, BASE_H = 1140, 760

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
        sr = globals().get('SimulationRenderer')
        if sr:
            if hasattr(sr, "_SCALED_BODY_CACHE"): sr._SCALED_BODY_CACHE = None
            if hasattr(sr, "_SCALED_CROSS_CACHE"): sr._SCALED_CROSS_CACHE = None

    @classmethod
    def to_screen(cls, x, y):
        return (int(x * cls.scale + cls.off_x), int(y * cls.scale + cls.off_y))

    @classmethod
    def to_world(cls, x, y):
        return (int((x - cls.off_x) / cls.scale), int((y - cls.off_y) / cls.scale))

    @classmethod
    def s(cls, val):
        return int(val * cls.scale)

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
    path = resource_path("fonts/NotoSansTC-Regular.ttf")
    if os.path.exists(path):
        try: return pygame.font.Font(path, size)
        except: pass
    for name in ["Microsoft JhengHei", "Arial Unicode MS", "Noto Sans TC"]:
        try: return pygame.font.SysFont(name, size, bold=bold)
        except: continue
    return pygame.font.SysFont(None, size, bold=bold)

@functools.lru_cache(maxsize=512)
def get_text_surf(text, font, col):
    return font.render(text, True, col)

def tc(surf, text, font, col, cx, cy, use_cache=True):
    s = get_text_surf(text, font, col) if use_cache else font.render(text, True, col)
    surf.blit(s, s.get_rect(center=(cx, cy)))

def tl(surf, text, font, col, x, y, use_cache=True):
    s = get_text_surf(text, font, col) if use_cache else font.render(text, True, col)
    surf.blit(s, (x, y))

F48 = load_font(85, True); F36 = load_font(70, True); F28 = load_font(58, True)
F22 = load_font(48, True); F18 = load_font(38); F15 = load_font(28, True); F13 = load_font(20, True)

# ── Synthesised Sound & Paths ────────────────────────────────────────────────
def resource_path(rel):
    if getattr(sys, 'frozen', False): return os.path.join(sys._MEIPASS, rel)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), rel)

SOUND_OK = False
SND_PERFECT = SND_GOOD = SND_FAIL = SND_SUCCESS = SND_ALARM = SND_CHARGE = SND_HOVER = SND_CLICK = None

def init_sounds():
    global SND_PERFECT, SND_GOOD, SND_FAIL, SND_SUCCESS, SND_ALARM, SND_CHARGE, SND_HOVER, SND_CLICK, SOUND_OK
    try:
        path_hit = resource_path("hit.wav")
        if os.path.exists(path_hit):
            SND_PERFECT = pygame.mixer.Sound(path_hit); SND_GOOD = pygame.mixer.Sound(path_hit)
            SND_GOOD.set_volume(0.5)
        path_fail = resource_path("fail.wav")
        if os.path.exists(path_fail): SND_FAIL = pygame.mixer.Sound(path_fail)
        path_succ = resource_path("success.wav")
        if os.path.exists(path_succ): SND_SUCCESS = pygame.mixer.Sound(path_succ)
        SOUND_OK = True
    except Exception as e: print(f"Heimlich sound init error: {e}")

def play(snd):
    if SOUND_OK and snd is not None:
        try: snd.play()
        except: pass

# ── Game Data ─────────────────────────────────────────────────────────────────
OBSTACLES = [
    {"id":"candy", "name":"硬糖果",   "max_progress":12, "color":(6,182,212)},
    {"id":"meat",  "name":"大塊牛排", "max_progress":21, "color":(245,158,11)},
    {"id":"mochi", "name":"黏性麻糬", "max_progress":30, "color":(217,70,239)},
]
PATIENT_TYPES = ["standard","standard","pregnant","obese"]
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
    if len(_RRECT_CACHE) > 1000:
        _RRECT_CACHE.clear()

def draw_icon(surf, type, x, y, size, col):
    s = LogicalScreen.s(size)
    h = s // 2
    if type == "trophy":
        pygame.draw.rect(surf, col, (x - h, y - h, s, s // 2), border_radius=s // 6)
        pygame.draw.circle(surf, col, (x, y), h // 2)
        pygame.draw.line(surf, col, (x, y), (x, y + h), 2)
        pygame.draw.line(surf, col, (x - h, y + h), (x + h, y + h), 3)
    elif type == "clock":
        pygame.draw.circle(surf, col, (x, y), h, 2)
        pygame.draw.line(surf, col, (x, y), (x, y - h + 4), 2)
        pygame.draw.line(surf, col, (x, y), (x + h - 6, y), 2)

_GLOW_CACHE = {}
def glow(surf, col, cx, cy, r, steps=4, a0=55):
    key = (col, r, steps, a0)
    if key not in _GLOW_CACHE:
        mr = r + steps * 6
        gs = pygame.Surface((mr * 2, mr * 2), pygame.SRCALPHA)
        for i in range(steps, 0, -1):
            rr = r + i * 6
            alpha = a0 // i
            pygame.draw.circle(gs, (*col, alpha), (mr, mr), rr)
        _GLOW_CACHE[key] = (gs, mr)
    gs, mr = _GLOW_CACHE[key]
    surf.blit(gs, (cx - mr, cy - mr))

def lerp(a, b, t):
    return a + (b - a) * t
def pulse_col(col, amt=40):
    f = 0.5 + 0.5 * math.sin(pygame.time.get_ticks() * 0.008)
    return tuple(min(255, max(0, c + int(f * amt))) for c in col)

# ── Sprite Particles & Popup ──────────────────────────────────────────────────
class Particle(pygame.sprite.Sprite):
    _alpha_cache = {}
    def __init__(self, x, y, col, speed=220, gravity=300, size=5, life=0.55):
        super().__init__()
        angle = random.uniform(0, math.tau); spd = random.uniform(speed * 0.4, speed)
        self.x, self.y = float(x), float(y)
        self.vx, self.vy = math.cos(angle) * spd, math.sin(angle) * spd
        self.col = col; self.size = random.randint(3, 6); self.life = self.max_life = life; self.gravity = gravity
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
        if self.life <= 0: self.kill()
        else:
            t = self.life / self.max_life; alpha_idx = max(0, min(10, int(t * 10)))
            self.image = Particle._alpha_cache[(self.col, self.size)][alpha_idx]
            self.rect.center = (int(self.x), int(self.y))

def burst(group, x, y, col, count=18, **kw):
    for _ in range(count): group.add(Particle(x, y, col, **kw))

class Popup:
    __slots__ = ("text", "col", "x", "y", "vy", "life", "max_life", "font", "_surf")
    def __init__(self, text, x, y, col, font=None, life=1.0, vy=-90):
        self.text = text; self.col = col; self.x, self.y = float(x), float(y); self.vy = float(vy); self.life = self.max_life = life
        self.font = font or F22; self._surf = get_text_surf(text, self.font, col)
    def update(self, dt): self.y += self.vy * dt; self.vy += 60 * dt; self.life -= dt
    def draw(self, surf):
        t = self.life / self.max_life; alpha = int(255 * min(t * 3, 1.0))
        self._surf.set_alpha(alpha); surf.blit(self._surf, self._surf.get_rect(center=(int(self.x), int(self.y))))

# ── Beat Bar & Classes ────────────────────────────────────────────────────────
class BeatBar:
    BAR_W=300; BAR_H=32; PERIOD=1.4
    def __init__(self): self.phase=0.0; self.speed=1.0/self.PERIOD; self.direction=1
    def reset(self,oid): speeds={"candy":0.68,"meat":0.90,"mochi":1.15}; self.speed=speeds.get(oid,0.8); self.phase=random.random(); self.direction=random.choice([-1,1])
    def update(self,dt):
        self.phase += self.speed * self.direction * dt
        if self.phase>=1.0: self.phase=1.0; self.direction=-1
        elif self.phase<=0.0: self.phase=0.0; self.direction=1
    def rate(self):
        p=self.phase
        if 0.38<=p<=0.62: return "perfect"
        if 0.22<=p<=0.78: return "good"
        return "miss"

class Game:
    def __init__(self):
        self.state = "start"
        self.t = 0.0
        self.particle_group = pygame.sprite.Group()
        self.popups = []
        self.beat_bar = BeatBar()
        self.shake_x = 0
        self.shake_y = 0
        self.shake_t = 0.0
        self.shake_str = 0
        self.fail_flash = 0.0
        self.hit_flash = 0.0
        self.trans_t = 0.0
        self.trans_dir = 0
        self._alarm_t = 0.0
        self.obstacle = OBSTACLES[0]
        self.patient_type = "standard"
        self._reset_vars()

    def _reset_vars(self):
        self.stage = "back"
        self.phase = "locate"
        self.oxygen = 100.0
        self.slap_count = 0
        self.thrust_count = 0
        self.global_progress = 0.0
        self.is_charging = False
        self.power = 0.0
        self.last_hovered_btn = None
        self.is_spot_found = False
        self.target_y = 60.0
        self.cursor_y_px = None
        self.combo = 0
        self.max_combo = 0
        self.total_hits = 0
        self.perfect_hits = 0
        self.good_hits = 0
        self.miss_count = 0
        self.elapsed = 0.0
        self._start_ms = 0
        self.message = "移動滑鼠尋找：兩肩胛骨之間"

    def start_game(self, p_type=None):
        self._reset_vars()
        self.patient_type = p_type or random.choice(PATIENT_TYPES)
        self.obstacle = random.choice(OBSTACLES).copy()
        self.obstacle["max_progress"] = random.randint(20, 30)
        self.state = "playing"
        self.t = 0.0
        self.particle_group.empty()
        self.popups.clear()
        self._start_ms = pygame.time.get_ticks()
        self.beat_bar.reset(self.obstacle["id"])

    def _shake(self, s=8, d=0.18):
        self.shake_str = s
        self.shake_t = d

    def _update_shake(self, dt):
        if self.shake_t > 0:
            self.shake_t -= dt
            mag = max(0, self.shake_str * (self.shake_t / 0.18))
            self.shake_x = random.randint(-int(mag), int(mag))
            self.shake_y = random.randint(-int(mag) // 2, int(mag) // 2)
        else:
            self.shake_x = 0
            self.shake_y = 0
    def trigger_back_slap(self):
        rate = self.beat_bar.rate()
        self.total_hits += 1
        cx, cy = BX, BY + int(self.target_y / 100 * BH)
        if rate == "perfect":
            pg = 2
            self.combo += 1
            self.perfect_hits += 1
            col = C["emerald"]
            play(SND_PERFECT)
            self._shake(12, 0.2)
            burst(self.particle_group, cx, cy, col, 20, speed=200)
        elif rate == "good":
            pg = 1
            self.combo += 1
            self.good_hits += 1
            col = C["amber"]
            play(SND_GOOD)
            self._shake(6, 0.13)
            burst(self.particle_group, cx, cy, col, 10, speed=130)
        else:
            pg = 0
            self.combo = 0
            self.miss_count += 1
            col = C["red"]
            play(SND_FAIL)
            self.oxygen = max(0, self.oxygen - 5)
            self.fail_flash = 0.35
            burst(self.particle_group, cx, cy, col, 8)
        
        msg = "+2 PERFECT!" if rate == "perfect" else ("+1 GOOD" if rate == "good" else "MISS!")
        self._popup(msg, cx, cy - 35, col)
        self.global_progress += pg
        if self.global_progress >= self.obstacle["max_progress"]:
            self._win()
            return
        
        self.slap_count += 1
        if self.slap_count >= 5:
            self._start_trans("front")

    def trigger_thrust_success(self):
        self.thrust_count += 1
        self.global_progress += 1
        self.total_hits += 1
        self.perfect_hits += 1
        self.combo += 1
        self.is_charging = False
        play(SND_PERFECT)
        self._shake(14, 0.22)
        if self.global_progress >= self.obstacle["max_progress"]:
            self._win()
            return
        if self.thrust_count >= 5:
            self._start_trans("back")
        else:
            self.phase = "locate"
            base_y = 65.0 if self.patient_type in ("pregnant", "obese") else 92.0
            self.target_y = base_y + random.uniform(-4, 4)

    def trigger_fail(self, r):
        self.is_charging = False
        self.combo = 0
        self.miss_count += 1
        self.oxygen = max(0, self.oxygen - 8)
        self.phase = "locate"
        self.message = f"失敗：{r}"
        self.fail_flash = 0.45
        play(SND_FAIL)
    def _start_trans(self, to):
        self.phase = "transition"
        self.trans_t = 0.55
        self.trans_dir = 1 if to == "front" else -1

    def _finish_trans(self):
        if self.trans_dir == 1:
            self.stage = "front"
            self.phase = "locate"
            self.thrust_count = 0
            self.target_y = 65.0 if self.patient_type in ("pregnant", "obese") else 92.0
        else:
            self.stage = "back"
            self.phase = "locate"
            self.slap_count = 0
            self.target_y = 60.0
        self.beat_bar.reset(self.obstacle["id"])

    def _win(self):
        self.state = "victory"
        self.elapsed = (pygame.time.get_ticks() - self._start_ms) / 1000.0
        play(SND_SUCCESS)

    def update(self, dt, mx, my):
        self.t += dt
        self.particle_group.update(dt)
        for p in self.popups:
            p.update(dt)
        self.popups = [p for p in self.popups if p.life > 0]
        self.fail_flash = max(0, self.fail_flash - dt)
        self._update_shake(dt)
        if self.state != "playing":
            return
        self.oxygen -= 1.5 * dt
        if self.oxygen <= 0:
            self.state = "gameover"
            self.elapsed = (pygame.time.get_ticks() - self._start_ms) / 1000.0
        self.beat_bar.update(dt)
        if self.is_charging and self.stage == "front":
            self.power += 300 * dt
            if self.power > 100:
                self.trigger_fail("用力過猛！")
        if self.phase == "transition":
            self.trans_t -= dt
            if self.trans_t <= 0:
                self._finish_trans()
            return
        if self.phase == "locate":
            bx0 = BX - BW // 2
            if bx0 <= mx <= bx0 + BW and BY <= my <= BY + BH:
                y_pct = (my - BY) / BH * 100
                self.is_spot_found = abs(y_pct - self.target_y) < (8 if self.stage == "back" else 5)
            else:
                self.is_spot_found = False
    def on_mouse_down(self, b):
        if self.state != "playing" or b != 1 or self.phase == "transition":
            return
        if self.phase == "locate" and self.is_spot_found:
            if self.stage == "back":
                self.phase = "slap"
            else:
                self.phase = "inward"
                self.is_charging = True
        elif self.stage == "back" and self.phase == "slap":
            self.trigger_back_slap()

    def on_mouse_up(self, b):
        if b == 1 and self.is_charging:
            self.is_charging = False
            if self.phase == "inward":
                self.trigger_fail("動作中斷！")
    def on_key_down(self,k):
        if self.state=="playing" and k==pygame.K_w and self.stage=="front" and self.is_charging:
            if 70<=self.power<=90: self.trigger_thrust_success()
            else: self.trigger_fail("力道錯誤！")
    def rating(self): acc=self.perfect_hits/max(1,self.total_hits); return "S" if acc>=0.8 else ("A" if acc>=0.65 else "B")
    def get_score(self): return int((self.perfect_hits/max(1,self.total_hits))*70)

class SimulationRenderer:
    _MAIN_BG = _FRONT_IMG = _BACK_IMG = _ILLUS_IMG = None
    @staticmethod
    def _load_bg():
        if SimulationRenderer._FRONT_IMG is not None: return
        try:
            SimulationRenderer._FRONT_IMG = pygame.image.load(resource_path("front.jpg")).convert()
            SimulationRenderer._BACK_IMG = pygame.image.load(resource_path("back.jpg")).convert()
            SimulationRenderer._MAIN_BG = pygame.image.load(resource_path("restaurant_bg.png")).convert()
            SimulationRenderer._ILLUS_IMG = pygame.image.load(resource_path("heimlich_simulator.png")).convert_alpha()
        except: pass
    @staticmethod
    def draw_background(surf, g):
        SimulationRenderer._load_bg()
        if SimulationRenderer._MAIN_BG: surf.blit(pygame.transform.scale(SimulationRenderer._MAIN_BG, surf.get_size()), (0, 0))
        else: surf.fill(C["bg"])
    @staticmethod
    def draw_body_panel(surf, g):
        bx_s, by_s = LogicalScreen.to_screen(BX-BW//2, BY); bw_s, bh_s = LogicalScreen.s(BW), LogicalScreen.s(BH); sx, sy = LogicalScreen.s(g.shake_x), LogicalScreen.s(g.shake_y)
        rrect(surf, C["panel"], (bx_s+sx, by_s+sy, bw_s, bh_s), LogicalScreen.s(24), 2, C["orange"] if g.stage=="back" else C["cyan"])
        img = SimulationRenderer._BACK_IMG if g.stage=="back" else SimulationRenderer._FRONT_IMG
        if img: surf.blit(pygame.transform.smoothscale(img, (bw_s, bh_s)), (bx_s+sx, by_s+sy))
        if g.is_spot_found and g.phase=="locate":
            ty = LogicalScreen.s(int(g.target_y/100*BH)); pygame.draw.line(surf, C["emerald"], (bx_s, by_s+sy+ty), (bx_s+bw_s, by_s+sy+ty), 2)
    @staticmethod
    def draw_hud(surf, g): tc(surf, f"氧氣: {int(g.oxygen)}%  得分: {g.get_score()}", F22, C["white"], surf.get_width()//2, 40)
    @staticmethod
    def draw_start_screen(surf, mx, my, t, g):
        SimulationRenderer.draw_background(surf, g)
        tc(surf, "哈姆立克模擬器", F48, C["white"], surf.get_width()//2, 150)
        btn = pygame.Rect(surf.get_width()//2-150, 450, 300, 60)
        is_hover = btn.collidepoint(mx, my); rrect(surf, C["panel2"] if is_hover else C["panel"], btn, 30, 2, C["cyan"])
        tc(surf, "開始演練", F28, C["white"], surf.get_width()//2, 480)
        return {"standard": btn}
    @staticmethod
    def draw_overlays(surf, g, mx, my):
        g.particle_group.draw(surf); [p.draw(surf) for p in g.popups]
        if g.state in ("victory", "gameover"):
            tc(surf, "任務完成" if g.state=="victory" else "任務失敗", F48, C["white"], surf.get_width()//2, 300)
            btn = pygame.Rect(surf.get_width()//2-100, 500, 200, 50); rrect(surf, C["emerald"], btn, 25); tc(surf, "返回選單", F22, C["white"], surf.get_width()//2, 525)
            return btn
    @staticmethod
    def draw_power_bar(surf, g): pass
    @staticmethod
    def draw_phase_bar(surf, g): tc(surf, g.message, F18, C["cyan"], surf.get_width()//2, 100)
    @staticmethod
    def draw_beat_bar(surf, g): pass

async def run_heimlich(screen, clock):
    init_sounds(); g = Game(); LogicalScreen.update(screen.get_width(), screen.get_height())
    while True:
        dt = clock.tick(60)/1000.0; r_mx, r_my = pygame.mouse.get_pos(); mx, my = LogicalScreen.to_world(r_mx, r_my)
        for e in pygame.event.get():
            if e.type == pygame.QUIT: return "quit"
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE: return "menu"
                g.on_key_down(e.key)
            if e.type == pygame.MOUSEBUTTONDOWN and e.button==1:
                if g.state=="start":
                    btns = SimulationRenderer.draw_start_screen(screen, r_mx, r_my, g.t, g)
                    if btns["standard"].collidepoint(r_mx, r_my): g.start_game()
                elif g.state in ("victory", "gameover"): return "menu"
                else: g.on_mouse_down(1)
            if e.type == pygame.MOUSEBUTTONUP and e.button==1: g.on_mouse_up(1)
        g.update(dt, mx, my); SimulationRenderer.draw_background(screen, g)
        if g.state=="start": btn_rect = SimulationRenderer.draw_start_screen(screen, r_mx, r_my, g.t, g)
        else:
            SimulationRenderer.draw_body_panel(screen, g); SimulationRenderer.draw_hud(screen, g)
            SimulationRenderer.draw_phase_bar(screen, g); SimulationRenderer.draw_overlays(screen, g, r_mx, r_my)
        pygame.display.flip(); await asyncio.sleep(0)