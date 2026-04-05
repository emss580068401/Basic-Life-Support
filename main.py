import pygame, sys, os, time, math, random, json, functools, subprocess

# [新增] 多模式啟動檢查：解決 PyInstaller --onefile 下 sys.executable 的路徑爭議
# 必須放在所有主視窗初始化之前
if __name__ == "__main__":
    if "--heimlich" in sys.argv:
        import heimlich_simulator
        heimlich_simulator.main()
        sys.exit()

def resource_path(rel):
    if getattr(sys, 'frozen', False):
        return os.path.join(sys._MEIPASS, rel)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), rel)

pygame.init()
pygame.mixer.init()

# === 視覺特效類別與變數 ===
class Particle:
    _surf_pool = {}   # size → 可重用的 SRCALPHA Surface（最多 5 種尺寸）
    def __init__(self, x, y, dx, dy, lifetime, color, size=3):
        self.x, self.y = x, y
        self.dx, self.dy = dx, dy
        self.lifetime = lifetime
        self.max_life = lifetime
        self.color = color
        self.size = size
    def update(self, dt):
        self.x += self.dx * dt
        self.y += self.dy * dt
        self.lifetime -= dt
        return self.lifetime > 0
    def draw(self, surf):
        alpha = int(max(0, min(255, (self.lifetime / self.max_life) * 255)))
        # [優化] 每種尺寸只建立一次 Surface，重複填充使用，避免每幀 new Surface
        if self.size not in Particle._surf_pool:
            Particle._surf_pool[self.size] = pygame.Surface(
                (self.size*2, self.size*2), pygame.SRCALPHA)
        s = Particle._surf_pool[self.size]
        s.fill((0, 0, 0, 0))
        pygame.draw.circle(s, (*self.color, alpha), (self.size, self.size), self.size)
        surf.blit(s, (int(self.x-self.size), int(self.y-self.size)))

particles = []
shake_amount = 0.0
shake_timer = 0.0

def add_shake(amt, dur):
    global shake_amount, shake_timer
    shake_amount = amt
    shake_timer = dur

def spawn_particles(x, y, color, count=10):
    for _ in range(count):
        particles.append(Particle(
            x, y, 
            random.uniform(-200, 200), random.uniform(-200, 200),
            random.uniform(0.4, 1.0),
            color,
            random.randint(2, 6)
        ))

def get_shake():
    if shake_timer > 0:
        return (random.uniform(-shake_amount, shake_amount), 
                random.uniform(-shake_amount, shake_amount))
    return (0, 0)

# === 視窗 ===
# 預設使用 800x480 解析度，並附加最大化全視窗屬性
WIDTH, HEIGHT = 800, 480
try:
    screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE | pygame.WINDOWMAXIMIZED)
except AttributeError:
    screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
pygame.display.set_caption("SoulPress CPR+AED v2.0")
clock = pygame.time.Clock()

# === 顏色 ===
BLACK  = (  0,   0,   0)
WHITE  = (255, 255, 255)
GREEN  = (  0, 220,  80)
RED    = (255,  60,  60)
YELLOW = (255, 210,   0)
CYAN   = (  0, 200, 255)
ORANGE = (255, 140,   0)
DARK   = ( 12,  12,  22)
PANEL  = ( 22,  22,  42)
ACCENT = ( 80, 160, 255)

# === 字型 ===
font_lg = pygame.font.SysFont("Microsoft JhengHei", 54, bold=True)
font_md = pygame.font.SysFont("Microsoft JhengHei", 34, bold=True)
font_msg= pygame.font.SysFont("Microsoft JhengHei", 28, bold=True)  # 新增: 訊息專用加大粗體
font_sm = pygame.font.SysFont("Microsoft JhengHei", 24)
font_xs = pygame.font.SysFont("Microsoft JhengHei", 18)

# === 音效 ===
current_bgm = "16bit_happy_bg_music.mp3"
pygame.mixer.music.load(resource_path(current_bgm))
pygame.mixer.music.set_volume(0.4)
pygame.mixer.music.play(-1)
hit_snd  = pygame.mixer.Sound(resource_path("hit.wav"))
fail_snd = pygame.mixer.Sound(resource_path("fail.wav"))
succ_snd = pygame.mixer.Sound(resource_path("success.wav"))
tie_snd  = pygame.mixer.Sound(resource_path("tie_snd.wav"))
hit_snd.set_volume(0.7); fail_snd.set_volume(0.6)
succ_snd.set_volume(0.8); tie_snd.set_volume(0.7)

# === 圖片載入 ===
bg_orig      = pygame.image.load(resource_path("background.png")).convert()
aed_orig     = pygame.image.load(resource_path("aed_icon.png")).convert_alpha()
soul1_o      = pygame.image.load(resource_path("soul1.png")).convert_alpha()
body1_o      = pygame.image.load(resource_path("body1.png")).convert_alpha()
succ1_o      = pygame.image.load(resource_path("success1.png")).convert_alpha()
soul2_o      = pygame.image.load(resource_path("soul2.png")).convert_alpha()
body2_o      = pygame.image.load(resource_path("body2.png")).convert_alpha()
succ2_o      = pygame.image.load(resource_path("success2.png")).convert_alpha()
sw1_o        = pygame.image.load(resource_path("success1_win.png")).convert_alpha()
sw2_o        = pygame.image.load(resource_path("success2_win.png")).convert_alpha()
# === 新美術素材 ===
menu_bg_o    = pygame.image.load(resource_path("menu_bg.png")).convert()
title_logo_o = pygame.image.load(resource_path("title_logo.png")).convert_alpha()
tut_icons_o  = pygame.image.load(resource_path("tutorial_icons.png")).convert_alpha()
rhy_bg_o     = pygame.image.load(resource_path("rhy_bg.png")).convert()
bpm_bg_o     = pygame.image.load(resource_path("bpm_bg.png")).convert()
emei_aed_bg_o = pygame.image.load(resource_path("emei_aed_bg.png")).convert()

def sscale(img, s):
    return pygame.transform.smoothscale(img,
        (int(img.get_width()*s), int(img.get_height()*s)))


# === 預先縮放（避免迴圈重建浪費效能）===
aed_icon_s   = sscale(aed_orig, 0.35)      # AED 小圖示（遊戲中提示用）
soul1        = sscale(soul1_o, 1.0)
body1        = sscale(body1_o, 1.5)
succ1_i      = sscale(succ1_o, 1.2)
soul2        = sscale(soul2_o, 1.0)
body2        = sscale(body2_o, 1.2)
succ2_i      = sscale(succ2_o, 1.2)
sw1_i        = sscale(sw1_o, 1.2)
sw2_i        = sscale(sw2_o, 1.2)
# 新美術素材縮放
menu_bg_img  = pygame.transform.scale(menu_bg_o, (max(1, WIDTH), max(1, HEIGHT)))  # 隨視窗調整
rhy_bg_img   = pygame.transform.scale(rhy_bg_o, (max(1, WIDTH), max(1, HEIGHT)))
bpm_bg_img   = pygame.transform.scale(bpm_bg_o, (max(1, WIDTH), max(1, HEIGHT)))
emei_aed_bg_img   = pygame.transform.smoothscale(emei_aed_bg_o, (max(1, WIDTH), max(1, HEIGHT)))
title_logo_i = pygame.transform.smoothscale(title_logo_o, (340, 340))  # 標題 logo
# tutorial_icons：手動精確對位 V5 版（參考 01.png ~ 06.png）
_TUT_COORDS = [
    (17,  341, 356, 355),  # 1. 安全警告 (01.png)
    (333, 30,  358, 358),  # 2. 檢查意識 (02.png)
    (674, 34,  322, 322),  # 3. 撥打119 (03.png)
    (672, 345, 335, 334),  # 4. 開始CPR (04.png)
    (343, 667, 338, 337),  # 5. AED儀器 (05.png)
    (691, 678, 321, 321),  # 6. 電擊/心臟 (06.png)
]

_icon_size = 170
TUT_ICONS = []
for _x, _y, _w, _h in _TUT_COORDS:
    _sub = tut_icons_o.subsurface((_x, _y, _w, _h))
    TUT_ICONS.append(pygame.transform.smoothscale(_sub, (_icon_size, _icon_size)))

# ============================================================
#  繪製輔助函式
# ============================================================
def draw_rrect(surf, color, rect, r=10, bw=0, bc=None):
    pygame.draw.rect(surf, color, rect, border_radius=r)
    if bw and bc:
        pygame.draw.rect(surf, bc, rect, bw, border_radius=r)

@functools.lru_cache(maxsize=1000)
def _cached_text(text, font, color):
    return font.render(text, True, color)

def draw_center(surf, text, font, color, cx, cy):
    s = _cached_text(text, font, color)
    surf.blit(s, (cx - s.get_width()//2, cy - s.get_height()//2))
    return s

@functools.lru_cache(maxsize=1000)
def _cached_text_fx(text, font, color, scale, glow_col, alpha):
    s = font.render(text, True, color)
    if alpha < 255: s.set_alpha(alpha)
    if scale != 1.0:
        w, h = s.get_size()
        s = pygame.transform.smoothscale(s, (int(w*scale), int(h*scale)))
    
    gs = None
    if glow_col:
        gs = font.render(text, True, glow_col)
        if alpha < 255: gs.set_alpha(alpha)
        if scale != 1.0:
            gw, gh = gs.get_size()
            gs = pygame.transform.smoothscale(gs, (int(gw*scale), int(gh*scale)))
            
    return s, gs

def draw_text_fx(surf, text, font, color, cx, cy, scale=1.0, glow_col=None, alpha=255):
    s, gs = _cached_text_fx(text, font, color, scale, glow_col, alpha)
    if gs:
        for off in [(1,1),(-1,1),(1,-1),(-1,-1),(0,2),(0,-2),(2,0),(-2,0)]:
            surf.blit(gs, (cx - gs.get_width()//2 + off[0], cy - gs.get_height()//2 + off[1]))
    surf.blit(s, (cx - s.get_width()//2, cy - s.get_height()//2))
    return s

def draw_bar(surf, x, y, w, h, prog, col, bg=(35,35,55)):
    pygame.draw.rect(surf, bg, (x, y, w, h), border_radius=h//2)
    fw = int(w * max(0.0, min(prog, 1.0)))
    if fw > 0:
        pygame.draw.rect(surf, col, (x, y, fw, h), border_radius=h//2)
    pygame.draw.rect(surf, WHITE, (x, y, w, h), 2, border_radius=h//2)

# ============================================================
#  遊戲常數
# ============================================================
MAX_TAPS  = 60
AED_RATIO = 0.5
BPM_MIN, BPM_MAX = 100, 120

P1_START_X = 150; P1_END = 150
P1_SOUL_YF = 0.84; P1_BODY_YF = 0.90
P2_START_X = 150; P2_END = 150
P2_SOUL_YF = 0.65; P2_BODY_YF = 0.74

P1_KEYS    = (pygame.K_a, pygame.K_s, pygame.K_d, pygame.K_w)
P1_AED_KEY = pygame.K_SPACE
P2_KEYS    = (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_UP, pygame.K_DOWN)
P2_AED_KEY = pygame.K_KP0

# ============================================================
#  教學步驟資料
# ============================================================
TUTORIAL_STEPS = [
    ("第1步：確認安全",   "確保現場環境安全，才能接近傷患"),
    ("第2步：叫叫CD",   "輕拍肩膀確認意識，大聲呼救求助"),
    ("第3步：撥打119",    "立刻通報，並請旁人去取 AED 回來"),
    ("第4步：開始CPR",    "雙手交疊，每分鐘 100～120 下按壓"),
    ("第5步：AED到達",    "開機，依語音指示貼上電擊貼片"),
    ("第6步：分析＆電擊","所有人離開，按電擊鍵後立即繼續CPR"),
]
TUT_COLORS = [GREEN, CYAN, YELLOW, RED, ORANGE, ACCENT]

# ============================================================
#  問答資料
# ============================================================
QUIZ_Q = [
    {"q":"CPR胸部按壓，每分鐘應按幾下？",
     "opts":["60～80下","80～100下","100～120下","120～140下"],
     "ans":2, "exp":"✅ 正確！國際標準為每分鐘 100～120 下"},
    {"q":"成人胸部按壓深度應達多少公分？",
     "opts":["1～2公分","2～3公分","5～6公分","8～10公分"],
     "ans":2, "exp":"✅ 正確！成人按壓深度為 5～6 公分"},
    {"q":"CPR 中按壓與吹氣的比例為何？",
     "opts":["10:1","15:1","30:2","30:4"],
     "ans":2, "exp":"✅ 正確！30次按壓 配合 2次人工呼吸"},
    {"q":"AED 的全名是什麼？",
     "opts":["自動體外心臟去顫器","自動心臟注射器","急救電擊棒","自動血壓計"],
     "ans":0, "exp":"✅ 正確！AED = Automated External Defibrillator"},
    {"q":"心跳停止後幾分鐘內電擊，存活率最高？",
     "opts":["10分鐘內","8分鐘內","5分鐘內","3分鐘內"],
     "ans":3, "exp":"✅ 正確！每延遲1分鐘存活率降約10%，3分鐘內最佳！"},
]

# ============================================================
#  選單項目
# ============================================================
MENU_ITEMS = [
    ("  單人 CPR 訓練",  "single"),
    ("  雙人競速對戰",  "dual"),
    ("  急救教學模式",  "tutorial"),
    ("  知識問答挑戰",  "quiz"),
    ("  BPM 節拍訓練",  "bpm"),
    ("  音遊節奏模式",  "rhythm"),
    ("  音遊進階挑戰",  "rhythm_adv"),
    ("  AED 操作模擬", "aed_sim"),
    ("  哈姆立克模擬",  "heimlich"),
    ("  排行榜榮譽榜",  "leaderboard"),
]

# ============================================================
#  遊戲狀態變數
# ============================================================
state     = "title"
game_mode = None    # "single" / "dual"
play_mode = None    # "time" / "rounds"
time_lim  = 0
round_goal = 0
buf       = ""

prepare_t  = None
prep_last_rem = -1
finish_t   = None
MIN_FINISH = 3

tc1=tc2=0
tt1=[]; tt2=[]
pd1=pd2=False
a1=a2=False
ok1=ok2=False
rc1=rc2=0
p1_rt=None; p2_rt=None
start_t=0
rsnd_played=False

menu_sel = 0
tut_step = 0
tut_anim = 0.0

quiz_idx  = 0
quiz_scr  = 0
quiz_ans  = False
quiz_sel  = -1
quiz_txt  = ""

bpm_times = []
bpm_cur   = 0
bpm_msg   = "按任意方向鍵開始練習！"

# === 音遊模式變數 ===
rhy_notes = []     # 存放下落音符：字典 { 'y': float, 'hit': bool }
rhy_score = 0
rhy_combo = 0
rhy_max_combo = 0
rhy_last_gen = 0
rhy_bpm = 110      # 110 BPM
rhy_speed = 350.0  # 像素/秒
rhy_start_t = 0
rhy_msg = ""
rhy_msg_t = 0
rhy_playing = False
rhy_duration = 30  # 遊戲時間 30 秒
rhy_target_y = 400 # 判定圈垂直位置
rhy_revived   = 0     # 累計救活人數
rhy_revive_t  = 0     # 救活動畫計時器
rhy_flash_a   = 0     # 閃白效果透明度
rhy_gauge     = 0     # 當前救護進度 (0-100)
rhy_perf_streak = 0    # 連續完美計數
rhy_hits_fx    = []    # 浮動分數特效列表 [{ 'val', 'x', 'y', 'a' }]
survival_pct   = 100.0 # 黃金 4 分鐘存活率
L_FILE         = "leaderboard.json" # 排行榜檔案
l_data         = []    # 暫存排行榜資料
is_new_record  = False # 是否打破紀錄標記
p_name         = ""    # 當前玩家名稱輸入緩衝
visual_pulse   = 0.0   # 隨節奏變動的數值 (0.0~1.0)
rhy_advanced   = False # 是否為進階模式 (組合鍵支援)
rhy_ecg_pts    = []    # 音遊專用心電圖點

# === AED 模擬變數 ===
aed_sub_state = "EXPOSE" # EXPOSE, OFF, ON, PADS, PLUG, ANALYZING, SHOCK_READY, COMPLETE
aed_timer     = 0
# 目標區域根據 aed_body 進行校正
aed_pads      = [
    {"pos": [40, 320], "target": (338, 144), "placed": False, "dragging": False, "label": "右上方胸部", "w": 80, "h": 100},
    {"pos": [40, 390], "target": (478, 257), "placed": False, "dragging": False, "label": "左下方腋下", "w": 100, "h": 80}
]
aed_shirt_rect  = pygame.Rect(WIDTH//2-110, HEIGHT//2-130, 220, 260) # 模擬上衣
aed_shirt_drag  = False
aed_shirt_gone  = False
aed_plug_pos    = [40, 100]
aed_plug_drag   = False
aed_plugged     = False
aed_ecg_pts   = []     # 存放心電圖動態點
aed_msg       = "請先拉開患者上衣"

anim_t = 0.0   # 全域動畫計時器
# 載入 AED 圖片素材
try:
    # [修正] 使用 resource_path，確保打包後也能正確載入
    aed_ui_o   = pygame.image.load(resource_path("aed_ui.png")).convert()
    aed_body_o = pygame.image.load(resource_path("aed_body.png")).convert()
    aed_ui_s   = pygame.transform.scale(aed_ui_o, (280, 280))
    aed_body_s = pygame.transform.scale(aed_body_o, (480, 480))
except Exception:
    aed_ui_s   = pygame.Surface((280, 280)); aed_ui_s.fill(ORANGE)
    aed_body_s = pygame.Surface((480, 480)); aed_body_s.fill(DARK)

# 定義按鈕與插槽在新 UI 上的相對位置
aed_ui_rect = pygame.Rect(WIDTH-290, 100, 280, 280)
aed_btn_pwr   = pygame.Rect(aed_ui_rect.x + 85,  aed_ui_rect.y + 85,  60, 60)
aed_btn_shk   = pygame.Rect(aed_ui_rect.x + 195, aed_ui_rect.y + 135, 75, 75)
aed_socket_rect = pygame.Rect(aed_ui_rect.x + 105, aed_ui_rect.y + 205, 45, 45)
aed_plug_target = (aed_socket_rect.centerx - 20, aed_socket_rect.centery - 20)

bg = pygame.transform.scale(bg_orig, (WIDTH, HEIGHT))
# 初始化持續性快取 Surface
overlay_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
f_ov_surf    = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
temp_screen  = pygame.Surface((WIDTH, HEIGHT))   # [優化] 震動效果重用 Surface，避免每幀 copy()
_lane_glow_cache = {}   # [優化] 軌道發光漸層快取 (glow_h, advanced) → Surface

# ============================================================
#  position_rects：依目前視窗尺寸計算角色座標
# ============================================================
def place_rects():
    global s1r, b1r, sc1r, s2r, b2r, sc2r, sw1r, sw2r
    s1r  = soul1.get_rect(center=(P1_START_X, int(HEIGHT*P1_SOUL_YF)))
    b1r  = body1.get_rect(center=(WIDTH-P1_END, int(HEIGHT*P1_BODY_YF)))
    sc1r = succ1_i.get_rect(center=(int(WIDTH*0.5), int(HEIGHT*0.5)))
    s2r  = soul2.get_rect(center=(P2_START_X, int(HEIGHT*P2_SOUL_YF)))
    b2r  = body2.get_rect(center=(WIDTH-P2_END, int(HEIGHT*P2_BODY_YF)))
    sc2r = succ2_i.get_rect(center=(int(WIDTH*0.5), int(HEIGHT*0.5)))
    sw1r = sw1_i.get_rect(center=(int(WIDTH*0.72), int(HEIGHT*0.5)))
    sw2r = sw2_i.get_rect(center=(int(WIDTH*0.28), int(HEIGHT*0.5)))

place_rects()

def reset_game():
    global tc1,tc2,tt1,tt2,pd1,pd2,a1,a2,ok1,ok2,rc1,rc2
    global p1_rt,p2_rt,start_t,rsnd_played,finish_t,survival_pct,p_name,is_new_record
    global rhy_score, rhy_combo, rhy_max_combo, rhy_revived, rhy_revive_t, rhy_flash_a, rhy_gauge, rhy_notes, rhy_msg, rhy_msg_t, rhy_perf_streak, rhy_hits_fx
    tc1=tc2=0; tt1.clear(); tt2.clear()
    pd1=pd2=a1=a2=ok1=ok2=False
    rc1=rc2=0; p1_rt=p2_rt=None
    rsnd_played=False; finish_t=None
    survival_pct = 100.0; p_name = ""; is_new_record = False
    # 音遊全變數重置與清空
    rhy_score=rhy_combo=rhy_max_combo=rhy_revived=rhy_revive_t=rhy_flash_a=rhy_gauge=rhy_perf_streak=0
    rhy_notes.clear(); rhy_msg=""; rhy_msg_t=0; rhy_hits_fx.clear()
    rhy_ecg_pts.clear()
    place_rects()
    start_t = time.time()

def load_l():
    global l_data
    try:
        if os.path.exists(L_FILE):
            with open(L_FILE, "r", encoding="utf-8") as f:
                l_data = json.load(f)
        else: l_data = []
    except: l_data = []

def save_l(name, score, revived):
    load_l()
    l_data.append({"name": name, "score": score, "revived": revived, "date": time.strftime("%Y-%m-%d")})
    # 根據使用者要求：得分優先排序
    l_data.sort(key=lambda x: x['score'], reverse=True)
    with open(L_FILE, "w", encoding="utf-8") as f:
        json.dump(l_data[:10], f, ensure_ascii=False, indent=4)

load_l() # 初始載入

# ============================================================
#  輔助函式：BPM 計算 / AED 重置 / 模式啟動（消除重複程式碼）
# ============================================================
def calc_bpm(times):
    """由時間戳陣列計算平均 BPM，至少需 2 個時間點"""
    if len(times) < 2:
        return 0.0
    iv = [times[i] - times[i-1] for i in range(1, len(times))]
    return 60.0 / (sum(iv) / len(iv))

def reset_aed_sim():
    """重置 AED 模擬器所有狀態變數（統一入口，消除六處重複初始化）"""
    global aed_sub_state, aed_timer, aed_msg
    global aed_shirt_gone, aed_plugged, aed_shirt_drag, aed_plug_drag
    aed_sub_state = "EXPOSE"; aed_timer = 0
    aed_msg = "第一步：請向兩側拖曳拉開患者上衣"
    aed_shirt_gone = False; aed_plugged = False
    aed_shirt_drag = False; aed_plug_drag = False
    aed_shirt_rect.update(WIDTH // 2 - 110, HEIGHT // 2 - 130, 220, 260)
    aed_plug_pos[:] = [40, 100]
    aed_pads[0]["pos"] = [40, 320]; aed_pads[0]["placed"] = False; aed_pads[0]["dragging"] = False
    aed_pads[1]["pos"] = [40, 390]; aed_pads[1]["placed"] = False; aed_pads[1]["dragging"] = False

def launch_mode(picked):
    """處理選單模式選擇，回傳 True 表示已處理（消除兩段重複的選單邏輯）"""
    global game_mode, state, buf, rhy_advanced, rhy_playing
    global quiz_idx, quiz_scr, quiz_ans, quiz_sel, quiz_txt
    global tut_step, tut_anim, bpm_cur, bpm_msg, menu_sel
    if picked in ("single", "dual"):
        game_mode = picked; state = "play_type"; buf = ""; return True
    elif picked == "tutorial":
        tut_step = 0; tut_anim = 0; state = "tutorial"; return True
    elif picked == "quiz":
        quiz_idx = quiz_scr = 0; quiz_ans = False; quiz_sel = -1; quiz_txt = ""
        state = "quiz"; return True
    elif picked == "bpm":
        bpm_times.clear(); bpm_cur = 0; bpm_msg = "按任意方向鍵開始練習！"
        state = "bpm_train"; return True
    elif picked == "aed_sim":
        reset_aed_sim(); state = "aed_sim"; return True
    elif picked in ("rhythm", "rhythm_adv"):
        game_mode = "rhythm"; rhy_advanced = (picked == "rhythm_adv")
        reset_game(); rhy_playing = False; state = "setup_time"; buf = ""; return True
    elif picked == "heimlich":
        # [優化] 視窗智慧切換啟動
        try:
            # 1. 暫停原本的背景音樂並最小化主選單，避免 Windows 判定為無回應
            pygame.mixer.music.pause()
            
            # 2. 啟動模式切換 (區分開發者模式與打包模式)
            if getattr(sys, 'frozen', False):
                # 【打包模式】呼叫自己並傳入 --heimlich 參數，繞過腳本定位錯誤
                subprocess.run([sys.executable, "--heimlich"])
            else:
                # 【開發模式】維持原始 python 腳本呼叫
                h_path = resource_path("heimlich_simulator.py")
                subprocess.run([sys.executable, h_path])
            
            # 3. 從子行程返回後，恢復主選單狀態
            pygame.mixer.music.unpause()
            # 重新刷一下視窗模式以確保焦點回歸大畫面
            pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE | pygame.WINDOWMAXIMIZED)
            state = "mode_select"; menu_sel = 8  # 回來後停留在原本的第 9 項
        except Exception as e:
            print(f"啟動模擬器失敗: {e}")
        return True
    elif picked == "leaderboard":
        load_l(); state = "leaderboard"; return True
    return False

# ============================================================
#  按鍵處理輔助：計算 BPM 並更新靈魂位置
# ============================================================
def handle_press(tt, tc, pd, a, sr, start_x, end_margin, s_pct=100.0):
    """回傳 (new_tc, new_pd, new_a, hit_ok)"""
    tt.append(time.time())
    if len(tt) > 5: tt.pop(0)
    if len(tt) >= 2:
        bpm = calc_bpm(tt)   # [優化] 改用統一的 calc_bpm()
        if BPM_MIN <= bpm <= BPM_MAX+0.5 and tc < MAX_TAPS:
            hit_snd.play()
            inc = 1
            if s_pct <= 0 and random.random() < 0.5: inc = 0
            tc += inc
            sr.centerx = int(start_x + ((WIDTH-end_margin) - start_x) * tc/MAX_TAPS)
            if tc >= MAX_TAPS * AED_RATIO and not a:
                return tc, True, True, True
            return tc, pd, a, True
        else:
            fail_snd.play()
    return tc, pd, a, False

# ============================================================
#  主迴圈
# ============================================================
running = True
prev_state = ""

while running:
    # 強制阻擋作業系統輸入法 (IME) 攔截遊戲控制鍵
    if state != prev_state:
        if state == "name_input":
            pygame.key.start_text_input()
        else:
            pygame.key.stop_text_input()
        prev_state = state

    dt  = clock.tick(60) / 1000.0
    now = time.time()
    anim_t += dt
    tut_anim += dt

    # === 動態切換背景音樂 ===
    req_bgm = "16bit_happy_bg_music.mp3"
    if game_mode == "rhythm" and state in ("setup_time", "prepare", "rhythm", "finish", "name_input"):
        req_bgm = "Steady_Hands_Clear_Path.mp3"
    
    if current_bgm != req_bgm:
        current_bgm = req_bgm
        pygame.mixer.music.load(resource_path(req_bgm))
        pygame.mixer.music.play(-1)

    # === 更新特效狀態 ===
    if shake_timer > 0:
        shake_timer -= dt
    else:
        shake_amount = 0
    
    for p in particles[:]:
        if not p.update(dt):
            particles.remove(p)
            
    # 視覺脈衝：隨 110 BPM 動態變化 (約 0.545 秒一拍)
    visual_pulse = 0.5 + 0.5 * math.sin(now * (110 / 60.0) * 2 * math.pi)

    # --------------------------------------------------
    #  黃金 4 分鐘存活率計時 (非線性衰減)
    # --------------------------------------------------
    if state in ("play", "rhythm"):
        elapsed = now - start_t
        if elapsed < 120: survival_pct = 100 - (elapsed / 120) * 20
        elif elapsed < 240: survival_pct = 80 - ((elapsed - 120) / 120) * 80
        else: survival_pct = 0
        
        # [核心修正] 同步全域 rhythm 判定高度與患者位置，解決不同解析度下的判定與特效位移
        if state == "rhythm":
            rhy_target_y = int(HEIGHT * 0.83)
            rhy_patient_x = int(WIDTH * 0.82)
            rhy_patient_y = HEIGHT - 200

    # --------------------------------------------------
    #  AED 模擬器狀態轉換邏輯與動態座標佈局
    # --------------------------------------------------
    if state == "aed_sim":
        # === 動態座標同步 (適應縮放機制與素材比例) ===
        # AED 移往畫面中央旁邊 (相對於畫面中央)
        aed_w, aed_h = 280, 280
        aed_x = WIDTH//2 + 80
        aed_y = max(20, HEIGHT//2 - 240)
        aed_ui_rect.update(aed_x, aed_y, aed_w, aed_h)
        
        # 根據新栽切的 AED 圖修改按鍵與插座中心 (依照裁切比例再次校正)：
        aed_btn_pwr.update(aed_ui_rect.x + 50, aed_ui_rect.y + 50, 50, 50) 
        aed_btn_shk.update(aed_ui_rect.x + 180, aed_ui_rect.y + 100, 70, 70)
        aed_socket_rect.update(aed_ui_rect.x + 70, aed_ui_rect.y + 180, 50, 50)
        aed_plug_target = (aed_socket_rect.centerx - 20, aed_socket_rect.centery - 20)
        
        # 工具箱在 AED 下方
        drawer_r = pygame.Rect(aed_x, aed_y + aed_h + 10, aed_w, HEIGHT - (aed_y + aed_h + 30))
        
        # 貼片與插頭若未拖曳 & 未放置，則乖乖待在右側工具箱內 (下移避免與標題重疊)
        if not aed_pads[0]["dragging"] and not aed_pads[0]["placed"]:
            aed_pads[0]["pos"] = [drawer_r.x + 30, drawer_r.y + 70]
        if not aed_pads[1]["dragging"] and not aed_pads[1]["placed"]:
            aed_pads[1]["pos"] = [drawer_r.x + 30, drawer_r.y + 190]
        if not aed_plug_drag and not aed_plugged:
            aed_plug_pos = [drawer_r.x + 180, drawer_r.y + 70]

        # 同步患者身體(胸部)與貼片目標點 - 置於畫面中間略偏左
        chest_cx = WIDTH//2 - 180
        chest_cy = HEIGHT//2 - 80
        body_r = aed_body_s.get_rect(center=(chest_cx, chest_cy))
        if not aed_shirt_drag:
            aed_shirt_rect.update(body_r.centerx - 110, body_r.centery - 130, 220, 260)
        # aed_body.png 上的十字座標
        # aed_body.png 上的十字座標 (已考慮直貼偏移)
        aed_pads[0]["target"] = (body_r.x + 137, body_r.y + 89)
        aed_pads[1]["target"] = (body_r.x + 252, body_r.y + 200)

        # 動態滑鼠游標 (指到可互動或拖曳物品時變為手型)
        mx, my = pygame.mouse.get_pos()
        hover = False
        if not aed_shirt_gone and aed_shirt_rect.collidepoint(mx, my): hover = True
        elif aed_sub_state == "PADS":
            for p in aed_pads:
                if not p["placed"] and not p["dragging"] and pygame.Rect(p["pos"][0], p["pos"][1], p["w"], p["h"]).collidepoint(mx, my):
                    hover = True
        elif aed_sub_state == "PLUG" and not aed_plugged:
            if not aed_plug_drag and pygame.Rect(aed_plug_pos[0], aed_plug_pos[1], 40, 40).collidepoint(mx, my):
                hover = True
        elif aed_sub_state == "OFF" and aed_btn_pwr.collidepoint(mx, my): hover = True
        elif aed_sub_state == "SHOCK_READY" and aed_btn_shk.collidepoint(mx, my): hover = True
        elif pygame.Rect(aed_ui_rect.centerx - 65, aed_ui_rect.top - 100, 130, 45).collidepoint(mx, my): hover = True
        
        if hover or aed_shirt_drag or aed_plug_drag or any(p["dragging"] for p in aed_pads):
            pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_HAND)
        else:
            pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_ARROW)

        aed_elapsed = time.time() - aed_timer
        if aed_sub_state == "ON":
            if aed_elapsed > 2.0:
                aed_sub_state = "PADS"
                aed_msg = "請撕開貼片，貼在患者右上方胸部與左下方腋下。"
        elif aed_sub_state == "ANALYZING":
            if aed_elapsed > 4.0:
                aed_sub_state = "SHOCK_READY"
                aed_msg = "分析完成！建議電擊。請按閃爍的橘色按鈕或 Space。"
                succ_snd.play()
        elif aed_sub_state == "COMPLETE":
            # 取消自動退回主選單，畫面保留至手動按下 ESC 為止
            pass

    # --------------------------------------------------
    #  事件處理
    # --------------------------------------------------
    for e in pygame.event.get():
        if e.type == pygame.QUIT:
            running = False

        elif e.type == pygame.VIDEORESIZE:
            WIDTH, HEIGHT = e.w, e.h
            screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
            bg = pygame.transform.scale(bg_orig, (WIDTH, HEIGHT))
            menu_bg_img = pygame.transform.scale(menu_bg_o, (max(1, WIDTH), max(1, HEIGHT)))
            rhy_bg_img = pygame.transform.scale(rhy_bg_o, (max(1, WIDTH), max(1, HEIGHT)))
            bpm_bg_img = pygame.transform.scale(bpm_bg_o, (max(1, WIDTH), max(1, HEIGHT)))
            emei_aed_bg_img = pygame.transform.smoothscale(emei_aed_bg_o, (max(1, WIDTH), max(1, HEIGHT)))
            # [優化] 重新分配快取 Surface
            overlay_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            f_ov_surf    = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            temp_screen  = pygame.Surface((WIDTH, HEIGHT))
            _lane_glow_cache.clear()   # 尺寸變了，清隤軌道漸層快取
            # [修正] 音遊模式目標高度必須也跟著動態更新，避免判定圈飛到天花板
            rhy_target_y = int(HEIGHT * 0.83)
            
            place_rects()

        elif e.type == pygame.KEYDOWN:

            # ESC：全域返回
            if e.key == pygame.K_ESCAPE:
                fail_snd.play()
                if state == "title":
                    running = False
                elif state == "mode_select":
                    state = "title"
                else:
                    state = "mode_select"; menu_sel = 0
                continue

            # ------ title ------
            if state == "title":
                if e.key in (pygame.K_RETURN, pygame.K_SPACE):
                    succ_snd.play()
                    state = "mode_select"

            # ------ mode_select ------
            elif state == "mode_select":
                if e.key == pygame.K_UP:
                    hit_snd.play()
                    menu_sel = (menu_sel-1) % len(MENU_ITEMS)
                elif e.key == pygame.K_DOWN:
                    hit_snd.play()
                    menu_sel = (menu_sel+1) % len(MENU_ITEMS)
                elif e.key in (pygame.K_RETURN, pygame.K_SPACE):
                    succ_snd.play()
                    _, picked = MENU_ITEMS[menu_sel]
                    launch_mode(picked)   # [優化] 統一入口，消除重複的 if/elif 連鎖
                # [優化] 數字快捷鍵支援 1-9 (1-9) 以及 0 (代表第 10 項)
                elif (pygame.K_1 <= e.key <= pygame.K_9) or (e.key == pygame.K_0):
                    succ_snd.play()
                    if e.key == pygame.K_0: menu_sel = 9
                    else: menu_sel = e.key - pygame.K_1
                    
                    if menu_sel < len(MENU_ITEMS):
                        _, picked = MENU_ITEMS[menu_sel]
                        launch_mode(picked)

            # ------ play_type ------
            elif state == "play_type":
                if e.key == pygame.K_t:
                    succ_snd.play()
                    state = "setup_time"; buf = ""
                elif e.key == pygame.K_r:
                    succ_snd.play()
                    state = "setup_rounds"; buf = ""

            # ------ setup_time / setup_rounds ------
            elif state in ("setup_time","setup_rounds"):
                if pygame.K_0 <= e.key <= pygame.K_9:
                    hit_snd.play()
                    buf += chr(e.key)
                elif e.key == pygame.K_BACKSPACE:
                    hit_snd.play()
                    buf = buf[:-1]
                elif e.key == pygame.K_RETURN and buf:
                    succ_snd.play()
                    v = int(buf)
                    if state == "setup_time":
                        play_mode = "time"; time_lim = v
                        prepare_t = time.time(); state = "prepare"
                    else:
                        play_mode = "rounds"; round_goal = v
                        reset_game(); state = "play"

            # ------ tutorial ------
            elif state == "tutorial":
                if e.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_RIGHT):
                    if tut_step < len(TUTORIAL_STEPS)-1:
                        hit_snd.play()
                        tut_step += 1; tut_anim = 0
                    else:
                        succ_snd.play()
                        state = "mode_select"
                elif e.key == pygame.K_LEFT and tut_step > 0:
                    hit_snd.play()
                    tut_step -= 1; tut_anim = 0

            # ------ quiz ------
            elif state == "quiz":
                if not quiz_ans:
                    if pygame.K_1 <= e.key <= pygame.K_4:
                        quiz_sel = e.key - pygame.K_1
                        q = QUIZ_Q[quiz_idx]
                        if quiz_sel == q["ans"]:
                            quiz_scr += 1; quiz_txt = q["exp"]
                            succ_snd.play()
                        else:
                            quiz_txt = f"❌ 正確答案：{q['opts'][q['ans']]}"
                            fail_snd.play()
                        quiz_ans = True
                else:
                    if e.key in (pygame.K_RETURN, pygame.K_SPACE):
                        hit_snd.play()
                        quiz_idx += 1; quiz_ans=False; quiz_sel=-1; quiz_txt=""
                        if quiz_idx >= len(QUIZ_Q):
                            state = "quiz_result"

            # ------ quiz_result ------
            elif state == "quiz_result":
                if e.key in (pygame.K_RETURN, pygame.K_SPACE):
                    succ_snd.play()
                    state = "mode_select"

            # ------ bpm_train ------
            elif state == "bpm_train":
                if e.key in P1_KEYS or e.key in P2_KEYS or e.key == pygame.K_SPACE:
                    bpm_times.append(time.time())
                    if len(bpm_times) > 8: bpm_times.pop(0)
                    if len(bpm_times) >= 2:
                        bpm_cur = int(calc_bpm(bpm_times))   # [優化] 改用統一的 calc_bpm()
                        if BPM_MIN <= bpm_cur <= BPM_MAX:
                            bpm_msg = f"🟢 完美！{bpm_cur} BPM — 繼續保持！"
                            hit_snd.play()
                        elif bpm_cur < BPM_MIN:
                            bpm_msg = f"🔴 {bpm_cur} BPM — 太慢了，請加快！"
                            fail_snd.play()
                        else:
                            bpm_msg = f"🟡 {bpm_cur} BPM — 稍微慢下來！"
                            fail_snd.play()
                
                # --- 排行榜與名稱輸入按鍵處理 ---
            elif state == "leaderboard":
                if e.key in (pygame.K_RETURN, pygame.K_SPACE):
                    succ_snd.play(); state = "mode_select"
            elif state == "name_input":
                if (pygame.K_a <= e.key <= pygame.K_z or pygame.K_0 <= e.key <= pygame.K_9):
                    if len(p_name) < 8:
                        hit_snd.play(); p_name += chr(e.key).upper()
                elif e.key == pygame.K_BACKSPACE:
                    hit_snd.play(); p_name = p_name[:-1]
                elif e.key == pygame.K_RETURN and p_name:
                    succ_snd.play()
                    s_ = rhy_score if game_mode=="rhythm" else rc1*1000
                    r_ = rhy_revived if game_mode=="rhythm" else rc1
                    save_l(p_name, s_, r_)
                    state = "leaderboard"

            # ------ rhythm ------
            elif state == "rhythm":
                if e.key in (pygame.K_RETURN, pygame.K_SPACE) and rhy_msg != "":
                    # 結算後返回選單
                    succ_snd.play()
                    state = "mode_select"; menu_sel = 0

                if rhy_playing:
                    # 定義按鍵對應的軌道 (0,1,2,3)
                    lane_idx = -1
                    if e.key in (pygame.K_LEFT, pygame.K_a): lane_idx = 0
                    elif e.key in (pygame.K_DOWN, pygame.K_s): lane_idx = 1
                    elif e.key in (pygame.K_UP, pygame.K_w): lane_idx = 2
                    elif e.key in (pygame.K_RIGHT, pygame.K_d): lane_idx = 3

                    if lane_idx != -1:
                        # 防作弊：統計當前按下的節奏鍵總數 (Mash Detection)
                        k_st = pygame.key.get_pressed()
                        mash_c = 0
                        for k in (pygame.K_LEFT, pygame.K_DOWN, pygame.K_UP, pygame.K_RIGHT, 
                                   pygame.K_a, pygame.K_s, pygame.K_w, pygame.K_d):
                            if k_st[k]: mash_c += 1
                        
                        # 尋找該軌道中最底下且未被 hit 的音符
                        hit_target = False
                        for note in rhy_notes:
                            if note.get('lane', 0) == lane_idx and not note['hit']:
                                dist = abs(note['y'] - rhy_target_y)
                                if dist < 50: # Hit range
                                    # [進階檢查] 是否為同步出現的組合鍵 (Chord)
                                    siblings = [n for n in rhy_notes if abs(n['y']-note['y']) < 1.5 and not n['hit']]
                                    chord_c  = len(siblings)
                                    
                                    # 防作弊核心：無論一般或進階模式，按壓總數若超過合理音符數即為作弊Mash
                                    max_allowed = chord_c if rhy_advanced else 1
                                    if mash_c > max_allowed:
                                        rhy_combo = 0; rhy_msg_t = time.time(); rhy_msg = "Mash!"
                                        for s in siblings: s['hit'] = True # 判定拔除避免重複計算
                                        survival_pct = max(0, survival_pct - 3.0)
                                        fail_snd.play(); hit_target = True; break
                                    
                                    if rhy_advanced and chord_c > 1:
                                        # 檢查是否所有對應按鍵都已按下
                                        all_down = True
                                        for s in siblings:
                                            sl = s['lane']
                                            needed = False
                                            if sl ==0 and (k_st[pygame.K_LEFT] or k_st[pygame.K_a]): needed=True
                                            elif sl==1 and (k_st[pygame.K_DOWN] or k_st[pygame.K_s]): needed=True
                                            elif sl==2 and (k_st[pygame.K_UP]   or k_st[pygame.K_w]): needed=True
                                            elif sl==3 and (k_st[pygame.K_RIGHT] or k_st[pygame.K_d]): needed=True
                                            if not needed: all_down = False; break
                                        if not all_down: 
                                            hit_target = True # 攔截預設的 Miss 判定
                                            break # 默默等待下個按鍵事件，防止爆出錯音

                                    # 判定成功：如果是組合鍵則整組處理
                                    hit_target = True
                                    hit_list = siblings if (rhy_advanced and chord_c > 1) else [note]
                                    for hn in hit_list: hn['hit'] = True
                                    
                                    g_inc = 0; added = 0
                                    # 以該軌道 X 為基準產生特效
                                    lane_x = WIDTH//2 + (lane_idx-1.5)*80
                                    eff = 1.0 if survival_pct > 20 else 0.5
                                    
                                    if dist < 20:
                                        rhy_perf_streak += 1
                                        bonus = min(200, (rhy_perf_streak-1) * 10)
                                        raw_added = 100 + bonus
                                        if chord_c > 1: raw_added *= chord_c # 組合鍵加倍
                                        added = int(raw_added * eff)
                                        rhy_score += added
                                        rhy_msg = "Perfect!" if chord_c==1 else f"Perfect x{chord_c}!"
                                        rhy_msg_t = time.time()
                                        g_inc = (3 * chord_c) * eff
                                        succ_snd.play()
                                        add_shake(4 + chord_c*3, 0.1) # 組合鍵更大震動
                                    else:
                                        rhy_perf_streak = 0
                                        added = int(50 * chord_c * eff)
                                        rhy_score += added
                                        rhy_msg = "Good!" if chord_c==1 else f"Good x{chord_c}!"
                                        rhy_msg_t = time.time()
                                        g_inc = (1 * chord_c) * eff
                                        hit_snd.play()
                                    
                                    # 新增浮動分數特效 (Hit Score Popup)
                                    rhy_hits_fx.append({'val': f"+{added}", 'x': lane_x, 'y': rhy_target_y, 'a': 255})
                                    
                                    rhy_combo += 1
                                    rhy_max_combo = max(rhy_max_combo, rhy_combo)
                                    # 累計救護進度 (分精度累長度)
                                    if rhy_revive_t <= 0: # 動態中不累計
                                        rhy_gauge += g_inc
                                        if rhy_gauge >= 100:
                                            rhy_gauge = 100
                                            rhy_revive_t = 1.8 # 觸發 1.8 秒動畫
                                            rhy_revived += 1
                                            rhy_score += 5000
                                            rhy_flash_a = 200 # 閃白起始強度
                                            add_shake(12, 0.4) # 救活時大震動
                                            spawn_particles(rhy_patient_x, rhy_patient_y, GREEN, 40)
                                            succ_snd.play()
                                    
                                    # 根據判定添加特效
                                    lane_cx = WIDTH//2 + (lane_idx-1.5)*80
                                    if dist < 20: 
                                        add_shake(4, 0.1)
                                        spawn_particles(lane_cx, rhy_target_y, YELLOW, 15)
                                    else:
                                        spawn_particles(lane_cx, rhy_target_y, WHITE, 8)
                                    
                                    break
                        if not hit_target: # 按錯時機 (Miss)
                            rhy_perf_streak = 0 # 中斷連續完美
                            rhy_combo = 0; rhy_msg_t = time.time()
                            rhy_msg = "Miss!"
                            fail_snd.play()

            # ------ play ------
            elif state == "play":
                if e.key == pygame.K_f:
                    if screen.get_flags() & pygame.FULLSCREEN:
                        screen = pygame.display.set_mode((WIDTH,HEIGHT), pygame.RESIZABLE)
                    else:
                        screen = pygame.display.set_mode((0,0), pygame.FULLSCREEN)
                    continue

                # P1 控制
                if ok1 and e.key in P1_KEYS:
                    tc1=0; tt1.clear(); pd1=a1=ok1=False; s1r.centerx=P1_START_X
                    continue
                if e.key == P1_AED_KEY and pd1:
                    pd1 = False; continue
                elif pd1 and e.key in P1_KEYS:
                    fail_snd.play(); continue
                elif not pd1 and e.key in P1_KEYS:
                    tc1, pd1, a1, _ = handle_press(tt1, tc1, pd1, a1, s1r, P1_START_X, P1_END, survival_pct)

                # P2 控制（僅雙打）
                if game_mode == "dual":
                    if ok2 and e.key in P2_KEYS:
                        tc2=0; tt2.clear(); pd2=a2=ok2=False; s2r.centerx=P2_START_X
                        continue
                    if e.key == P2_AED_KEY and pd2:
                        pd2 = False; continue
                    elif pd2 and e.key in P2_KEYS:
                        fail_snd.play(); continue
                    elif not pd2 and e.key in P2_KEYS:
                        tc2, pd2, a2, _ = handle_press(tt2, tc2, pd2, a2, s2r, P2_START_X, P2_END, survival_pct)

            # ------ finish 等待倒數 ------
            elif state == "finish":
                if e.key in (pygame.K_RETURN, pygame.K_SPACE):
                    succ_snd.play()
                    if is_new_record: state = "name_input"
                    else: state = "mode_select"; menu_sel = 0

            # ------ aed_sim ------
            elif state == "aed_sim":
                if e.key == pygame.K_SPACE and aed_sub_state == "SHOCK_READY":
                    succ_snd.play()
                    aed_sub_state = "COMPLETE"
                    aed_msg = "電擊完成！請立即繼續進行 CPR 按壓。"
                    aed_timer = time.time()
                    add_shake(25, 0.6) # AED 電擊強烈震動
                    spawn_particles(WIDTH//2 - 180, HEIGHT//2 - 80, CYAN, 60) # 電擊火花

        elif e.type == pygame.MOUSEBUTTONDOWN:
            if state == "aed_sim":
                mx, my = pygame.mouse.get_pos()
                
                # 0. 重置按鈕 (重新開始操作，移至 AED 主機上方)
                if pygame.Rect(aed_ui_rect.centerx - 65, aed_ui_rect.top - 100, 130, 45).collidepoint(mx, my):
                    succ_snd.play()
                    reset_aed_sim()   # [優化] 統一使用 reset_aed_sim()
                    continue

                # 1. 電源鍵 (僅在 EXPOSE 完成後可用)
                if aed_btn_pwr.collidepoint(mx, my):
                    if aed_sub_state == "OFF":
                        hit_snd.play()
                        aed_sub_state = "ON"
                        aed_msg = "AED 已啟動，請觀察指示語音。"
                        aed_timer = time.time()
                # 1.5 電擊鍵 (僅在 SHOCK_READY 可用)
                if aed_btn_shk.collidepoint(mx, my):
                    if aed_sub_state == "SHOCK_READY":
                        succ_snd.play()
                        aed_sub_state = "COMPLETE"
                        aed_msg = "電擊完成！請立即繼續進行 CPR 按壓。"
                        aed_timer = time.time()
                        add_shake(25, 0.6) # 電擊震動
                        spawn_particles(WIDTH//2 - 180, HEIGHT//2 - 80, CYAN, 60)
                # 2. 拉開上衣開始
                if aed_sub_state == "EXPOSE":
                    if aed_shirt_rect.collidepoint(mx, my):
                        aed_shirt_drag = True
                # 3. 貼片拖曳開始
                if aed_sub_state == "PADS":
                    for p in aed_pads:
                        p_rect = pygame.Rect(p["pos"][0], p["pos"][1], p["w"], p["h"])
                        if p_rect.collidepoint(mx, my) and not p["placed"]:
                            p["dragging"] = True
                            break
                # 4. 插頭拖曳開始
                if aed_sub_state == "PLUG":
                    plug_rect = pygame.Rect(aed_plug_pos[0], aed_plug_pos[1], 40, 40)
                    if plug_rect.collidepoint(mx, my):
                        aed_plug_drag = True

        elif e.type == pygame.MOUSEMOTION:
            if state == "aed_sim":
                mx, my = pygame.mouse.get_pos()
                if aed_shirt_drag:
                    aed_shirt_rect.x = mx - 100
                if aed_plug_drag:
                    aed_plug_pos = [mx - 20, my - 20]
                for p in aed_pads:
                    if p["dragging"]:
                        p["pos"] = [mx - 50, my - 40]

        elif e.type == pygame.MOUSEBUTTONUP:
            if state == "aed_sim":
                if aed_shirt_drag:
                    aed_shirt_drag = False
                    if abs(aed_shirt_rect.centerx - WIDTH//2) > 150:
                        aed_shirt_gone = True
                        aed_sub_state = "OFF"
                        aed_msg = "已露出胸部，請按下 AED 電源鍵開機。"
                        succ_snd.play()
                
                if aed_plug_drag:
                    aed_plug_drag = False
                    # 檢查插槽
                    dist = math.sqrt((aed_plug_pos[0]-aed_plug_target[0])**2 + (aed_plug_pos[1]-aed_plug_target[1])**2)
                    if dist < 60:
                        aed_plug_pos = list(aed_plug_target)
                        aed_plugged = True
                        succ_snd.play()
                        aed_sub_state = "ANALYZING"
                        aed_msg = "插頭已連接。正在分析心律，請勿碰觸患者！"
                        aed_timer = time.time()
                    else:
                        aed_plug_pos = [40, 100]
                        fail_snd.play()
                for p in aed_pads:
                    if p["dragging"]:
                        p["dragging"] = False
                        tx, ty = p["target"]
                        dist = math.sqrt((p["pos"][0]-tx)**2 + (p["pos"][1]-ty)**2)
                        if dist < 80: # 稍微放寬貼合判定的範圍，提升流暢度
                            p["pos"] = [tx, ty]
                            p["placed"] = True
                            succ_snd.play()
                            if all(pd["placed"] for pd in aed_pads):
                                aed_sub_state = "PLUG"
                                aed_msg = "貼片已就位，請將電擊導線插頭 (🔌) 插入 AED 插槽。"
                        else:
                            if p["label"] == "右上方胸部": p["pos"] = [40, 320]
                            else: p["pos"] = [40, 390]
                            fail_snd.play()

    # --------------------------------------------------
    #  prepare 倒數（事件迴圈外處理，避免 continue 跳過）
    # --------------------------------------------------
    if state == "prepare":
        elapsed   = now - prepare_t
        countdown = 3 - int(elapsed)
        screen.fill(DARK)
        if countdown > 0:
            if countdown != prep_last_rem:
                prep_last_rem = countdown
                hit_snd.play()
                
            draw_center(screen, "預備...", font_md, WHITE, WIDTH//2, HEIGHT//2-70)
            num_s = font_lg.render(str(countdown), True, YELLOW)
            # 脈衝縮放
            pulse = 1.0 + 0.15*math.sin(anim_t*8)
            num_p = pygame.transform.rotozoom(num_s, 0, pulse)
            screen.blit(num_p, (WIDTH//2-num_p.get_width()//2, HEIGHT//2-num_p.get_height()//2+10))
        else:
            succ_snd.play()
            prep_last_rem = -1
            if game_mode == "rhythm":
                rhy_duration = time_lim if time_lim > 0 else 30
                rhy_playing = True
                rhy_start_t = time.time()
                rhy_last_gen = time.time()
                state = "rhythm"
            else:
                reset_game(); state = "play"
        pygame.display.flip(); continue # 此處 continue 在 while True 內有效

    # ==================================================
    #  渲染
    # ==================================================
    screen.fill(DARK)

    # ====== 標題畫面 ======
    if state == "title":
        # 背景圖（menu_bg 都市夜景）
        screen.blit(menu_bg_img, (0, 0))
        # 暗化覆蓋 ─ [優化] 複用 overlay_surf，不每幀 new Surface
        overlay_surf.fill((0, 0, 20, 160))
        screen.blit(overlay_surf, (0, 0))

        # Title Logo 圖（置中偏上）
        logo_x = WIDTH//2 - title_logo_i.get_width()//2
        logo_y = 10
        screen.blit(title_logo_i, (logo_x, logo_y))

        # 漸強標題文字
        pulse  = 0.5 + 0.5*math.sin(anim_t*2.0)
        tc_val = (int(80+100*pulse), int(140+60*pulse), 255)
        draw_center(screen, "SoulPress", font_lg, tc_val, WIDTH//2, HEIGHT-170)
        draw_center(screen, "CPR + AED 急救推廣遊戲", font_md, CYAN, WIDTH//2, HEIGHT-120)
        draw_center(screen, "v2.0  | 新竹縣消防局", font_sm, (180,180,220), WIDTH//2, HEIGHT-82)

        if int(anim_t*1.8) % 2 == 0:
            draw_center(screen, "按 Enter 或 Space 開始", font_sm, WHITE, WIDTH//2, HEIGHT-45)
        draw_center(screen, "ESC 退出", font_xs, (120,120,155), WIDTH//2, HEIGHT-20)

    # ====== 模式選單 ======
    elif state == "mode_select":
        screen.blit(menu_bg_img, (0, 0))
        overlay_surf.fill((0, 0, 15, 195))   # [優化] 複用
        screen.blit(overlay_surf, (0, 0))

        draw_center(screen, "選擇遊戲模式", font_md, CYAN, WIDTH//2, 38)
        for i, (label, _) in enumerate(MENU_ITEMS):
            y   = 85 + i*68
            sel = (i == menu_sel)
            rect = pygame.Rect(WIDTH//2-240, y, 480, 56)
            bgc  = (40,70,140,220) if sel else (18,18,40,200)
            bdc  = CYAN            if sel else (55,55,80)
            draw_rrect(screen, (40,70,140) if sel else (18,18,40), rect, 10, 2, bdc)
            ns = font_sm.render(f"[{i+1}]", True, YELLOW if sel else (100,100,130))
            screen.blit(ns, (rect.x+10, rect.y+16))
            ts = font_md.render(label, True, WHITE if sel else (170,170,195))
            screen.blit(ts, (rect.x+50, rect.y+10))
            if sel:
                # 選中項目右側加三角形指示
                pts = [(rect.right-20, rect.centery),
                       (rect.right-30, rect.centery-7),
                       (rect.right-30, rect.centery+7)]
                pygame.draw.polygon(screen, CYAN, pts)
        draw_center(screen, "↑ ↓ 選擇   Enter 確認   ESC 返回", font_xs, (120,120,160), WIDTH//2, HEIGHT-22)

    # ====== 選擇賽制 ======
    elif state == "play_type":
        screen.blit(menu_bg_img, (0, 0))
        overlay_surf.fill((0, 0, 15, 195))   # [優化] 複用
        screen.blit(overlay_surf, (0, 0))

        draw_center(screen, "選擇賽制", font_md, CYAN, WIDTH//2, HEIGHT//2-90)
        for label, key, rect in [
            ("[T] 限時賽", "T", pygame.Rect(WIDTH//2-210, HEIGHT//2-30, 190, 64)),
            ("[R] 局數賽", "R", pygame.Rect(WIDTH//2+20,  HEIGHT//2-30, 190, 64)),
        ]:
            draw_rrect(screen, (40,75,140), rect, 12, 2, ACCENT)
            draw_center(screen, label, font_md, WHITE, rect.centerx, rect.centery)
        draw_center(screen, "ESC 返回", font_xs, (80,80,110), WIDTH//2, HEIGHT-25)

    elif state in ("setup_time","setup_rounds"):
        screen.blit(menu_bg_img, (0, 0))
        overlay_surf.fill((0, 0, 15, 195))   # [優化] 複用
        screen.blit(overlay_surf, (0, 0))

        lbl = "請輸入秒數：" if state=="setup_time" else "請輸入目標局數："
        draw_center(screen, lbl, font_md, CYAN, WIDTH//2, HEIGHT//2-70)
        inp_r = pygame.Rect(WIDTH//2-120, HEIGHT//2-20, 240, 64)
        draw_rrect(screen, PANEL, inp_r, 12, 2, ACCENT)
        draw_center(screen, buf + "_", font_lg, WHITE, WIDTH//2, HEIGHT//2+12)
        draw_center(screen, "Enter 確認   Backspace 刪除   ESC 返回", font_xs, (80,80,110), WIDTH//2, HEIGHT-25)

    # ====== 急救教學 ======
    elif state == "tutorial":
        title_t, body_t = TUTORIAL_STEPS[tut_step]
        tc  = TUT_COLORS[tut_step]

        # 關卡背景
        card = pygame.Rect(50, 36, WIDTH-100, HEIGHT-65)
        draw_rrect(screen, (16,16,36), card, 18, 3, tc)

        # 步驟指示點新位置
        dots_total = len(TUTORIAL_STEPS)
        dx = WIDTH//2 - dots_total*16
        for i in range(dots_total):
            c = tc if i == tut_step else (50,50,70)
            pygame.draw.circle(screen, c, (dx + i*32, card.y+16), 8 if i==tut_step else 5)

        # 步驟圖示（左側居中）
        fade = min(1.0, tut_anim*3)
        icon_surf = TUT_ICONS[tut_step]
        # fade-in 透明度
        if fade < 1.0:
            icon_surf = icon_surf.copy()
            icon_surf.set_alpha(int(255*fade))
        icon_x = card.x + 60
        icon_y = card.y + (card.height - icon_surf.get_height()) // 2
        screen.blit(icon_surf, (icon_x, icon_y))

        # 右側標題 + 說明
        text_x = icon_x + icon_surf.get_width() + 30
        text_w = card.right - text_x - 20
        title_col = tuple(int(c*fade) for c in tc)
        ts = font_lg.render(title_t, True, title_col)
        screen.blit(ts, (text_x, card.y + 55))

        body_col = tuple(int(220*fade) for _ in range(3))
        bs = font_md.render(body_t, True, body_col)
        screen.blit(bs, (text_x, card.y + 120))

        # 心跳動畫（居中底部）
        hr2 = int(10+5*abs(math.sin(tut_anim*4)))
        pygame.draw.circle(screen, RED, (WIDTH//2, card.bottom-22), hr2)
        pygame.draw.circle(screen, (255,100,100), (WIDTH//2, card.bottom-22), hr2-3)

        draw_center(screen, "← 上一步   → / Enter 下一步   ESC 返回", font_xs, (100,100,140), WIDTH//2, HEIGHT-18)

    # ====== 問答模式 ======
    elif state == "quiz":
        q = QUIZ_Q[quiz_idx]
        draw_center(screen, f"第 {quiz_idx+1}/{len(QUIZ_Q)} 題   得分：{quiz_scr}", font_sm, CYAN, WIDTH//2, 28)
        qs = font_md.render(q["q"], True, WHITE)
        screen.blit(qs, (WIDTH//2-qs.get_width()//2, 58))

        for i, opt in enumerate(q["opts"]):
            y    = 120 + i*72
            rect = pygame.Rect(WIDTH//2-280, y, 560, 60)
            if quiz_ans:
                if i == q["ans"]:  bgc=(0,90,35);  bdc=GREEN
                elif i==quiz_sel:  bgc=(90,0,0);   bdc=RED
                else:              bgc=PANEL;       bdc=(50,50,70)
            else:
                bgc=(45,70,120) if i==quiz_sel else PANEL
                bdc=ACCENT      if i==quiz_sel else (50,50,70)
            draw_rrect(screen, bgc, rect, 10, 2, bdc)
            ns = font_sm.render(f"[{i+1}]", True, YELLOW)
            screen.blit(ns, (rect.x+10, rect.y+16))
            os_ = font_md.render(opt, True, WHITE)
            screen.blit(os_, (rect.x+52, rect.y+12))

        if quiz_ans:
            col = GREEN if "✅" in quiz_txt else RED
            es  = font_sm.render(quiz_txt, True, col)
            screen.blit(es, (WIDTH//2-es.get_width()//2, HEIGHT-55))
            draw_center(screen, "按 Enter 下一題", font_xs, (80,80,110), WIDTH//2, HEIGHT-28)
        else:
            draw_center(screen, "按 1～4 選擇答案   ESC 返回", font_xs, (80,80,110), WIDTH//2, HEIGHT-25)

    # ====== 問答結果 ======
    elif state == "quiz_result":
        total = len(QUIZ_Q)
        pct   = quiz_scr / total
        draw_center(screen, "問答結果", font_lg, YELLOW, WIDTH//2, 70)
        draw_center(screen, f"答對 {quiz_scr} / {total} 題", font_md, WHITE, WIDTH//2, 145)
        if pct == 1.0:
            grade, gc = "滿分！急救達人 🏅", GREEN
        elif pct >= 0.6:
            grade, gc = "良好！繼續加油 💪", CYAN
        else:
            grade, gc = "多練習！生命需要你 ❤", ORANGE
        draw_center(screen, grade, font_md, gc, WIDTH//2, 200)
        draw_bar(screen, WIDTH//2-200, 250, 400, 24, pct, GREEN)
        draw_center(screen, f"{int(pct*100)}%", font_sm, WHITE, WIDTH//2, 292)
        draw_center(screen, "按 Enter 返回選單", font_sm, (80,80,110), WIDTH//2, HEIGHT-40)

    # ====== BPM 訓練器 ======
    elif state == "bpm_train":
        screen.blit(bpm_bg_img, (0, 0))
        overlay_surf.fill((0, 0, 15, 170))   # [優化] 複用
        screen.blit(overlay_surf, (0, 0))

        draw_center(screen, "BPM 節拍訓練器", font_md, CYAN, WIDTH//2, 36)
        draw_center(screen, "目標：100 ～ 120 BPM（標準按壓頻率）", font_sm, (140,140,180), WIDTH//2, 76)

        # BPM 大字 (隨節奏脈衝縮放)
        if bpm_cur > 0:
            bc = GREEN if BPM_MIN<=bpm_cur<=BPM_MAX else (ORANGE if bpm_cur<BPM_MIN else RED)
        else:
            bc = (70,70,90)

        bpm_font_p = 1.0 + visual_pulse * 0.1
        bpm_text = f"{bpm_cur} BPM" if bpm_cur>0 else "--- BPM"
        draw_text_fx(screen, bpm_text, font_lg, bc, WIDTH//2, HEIGHT//2-80, scale=bpm_font_p, glow_col=(*bc, 50))

        # 儀表條
        bx,by,bw,bh = WIDTH//2-210, HEIGHT//2+20, 420, 28
        pygame.draw.rect(screen, (35,35,55), (bx,by,bw,bh), border_radius=14)
        BPM_RANGE = 120   # 60 ~ 180
        ts = int((BPM_MIN-60)/BPM_RANGE*bw)
        te = int((BPM_MAX-60)/BPM_RANGE*bw)
        pygame.draw.rect(screen, (0,80,25), (bx+ts,by,te-ts,bh), border_radius=6)
        if bpm_cur > 0:
            px = int((min(max(bpm_cur,60),180)-60)/BPM_RANGE*bw)
            pygame.draw.circle(screen, bc, (bx+px, by+bh//2), 13)
        pygame.draw.rect(screen, WHITE, (bx,by,bw,bh), 2, border_radius=14)

        for lv in [60,80,100,120,140,160,180]:
            lx = int((lv-60)/BPM_RANGE*bw)+bx
            ls = font_xs.render(str(lv), True, (100,100,130))
            screen.blit(ls, (lx-ls.get_width()//2, by+bh+4))

        ms = font_sm.render(bpm_msg, True, WHITE)
        screen.blit(ms, (WIDTH//2-ms.get_width()//2, HEIGHT//2+80))
        draw_center(screen, "任意方向鍵 / WASD / Space 按壓   ESC 返回", font_xs, (80,80,110), WIDTH//2, HEIGHT-25)

    # ====== 音遊節奏模式 (Rhythm CPR) ======
    elif state == "rhythm":
        # 繪製 Nano Banana Pro 產生的酷炫背景，並鋪上暗色遮罩
        screen.blit(rhy_bg_img, (0, 0))
        overlay_surf.fill((0, 0, 15, 170))
        screen.blit(overlay_surf, (0, 0))

        title_str = "音遊進階挑戰 (110 BPM)" if rhy_advanced else "音遊節奏模式 (110 BPM)"
        draw_center(screen, title_str, font_md, YELLOW if rhy_advanced else CYAN, WIDTH//2, 36)

        # [修正] c_lv 提前計算，ECG 色彩選擇與後續邏輯皆依賴它
        c_lv = 0
        if rhy_combo >= 30: c_lv = 3
        elif rhy_combo >= 15: c_lv = 2
        elif rhy_combo >= 5: c_lv = 1

        # --- 背景與動態 ECG 視覺強化 ---
        f_ov_surf.fill((0, 0, 0, 0))
        
        # 1. 背景脈衝特效 (Fever)
        if c_lv >= 2:
            pulse_a = int(20 + 20 * math.sin(time.time() * 15)) if c_lv >= 3 else int(12 + 12 * math.sin(time.time() * 10))
            f_col = (255, 180, 0, pulse_a) if c_lv >= 3 else (0, 200, 255, pulse_a)
            f_ov_surf.fill(f_col)

        # 2. 動態 ECG 計算與繪製
        ecg_y_base = HEIGHT // 2 + 20
        spike = 0
        ecg_thickness = 2
        ecg_col = (0, 255, 150, 100)
        draw_glow = False

        if rhy_revive_t > 0:
            # 重生脈衝：強烈的寬幅震盪與高亮青色
            ecg_col = (0, 255, 255, 255)
            ecg_thickness = 4
            draw_glow = True
            spike_amp = 180 * (rhy_revive_t / 1.8)
            spike = math.sin((1.8 - rhy_revive_t) * 25) * spike_amp
            spike += random.uniform(-30, 30) * (rhy_revive_t / 1.8)
            
        elif rhy_combo == 0 and (now - rhy_start_t > 3.0):
            # 節奏錯誤或中斷：雜亂且發出紅光 (警告)
            ecg_col = (255, 40, 40, 200)
            ecg_thickness = 3
            draw_glow = True
            if visual_pulse > 0.5:
                spike = random.uniform(-60, 60)
            else:
                spike = random.uniform(-15, 15)
                
        else:
            # 正常與完美節奏
            if rhy_perf_streak >= 5: # 連續完美，展現金黃色穩態特效
                ecg_col = (255, 220, 0, 200)
                ecg_thickness = 3
                draw_glow = True
                if visual_pulse > 0.85: spike = (visual_pulse - 0.85) * 450
                elif visual_pulse > 0.7: spike = -(visual_pulse - 0.7) * 120
            else:
                ecg_col = (0, 255, 150, 120) if c_lv < 2 else (0, 200, 255, 160)
                if visual_pulse > 0.85: spike = (visual_pulse - 0.85) * 400
                elif visual_pulse > 0.7: spike = -(visual_pulse - 0.7) * 100

        rhy_ecg_pts.append(spike)
        if len(rhy_ecg_pts) > WIDTH // 4: rhy_ecg_pts.pop(0)

        if len(rhy_ecg_pts) >= 2:
            pts = [(i * 4, ecg_y_base - rhy_ecg_pts[i]) for i in range(len(rhy_ecg_pts))]
            if draw_glow:
                glow_col = (*ecg_col[:3], max(20, ecg_col[3] // 4))
                pygame.draw.lines(f_ov_surf, glow_col, False, pts, ecg_thickness + 6)
                pygame.draw.lines(f_ov_surf, glow_col, False, pts, ecg_thickness + 2)
            pygame.draw.lines(f_ov_surf, ecg_col, False, pts, ecg_thickness)
            
        # 繪製 ECG 與 Fever Layer 到主畫面
        screen.blit(f_ov_surf, (0,0))

        # --- 生存率 HUD ---
        s_base_col = GREEN if survival_pct > 60 else (ORANGE if survival_pct > 20 else RED)
        if survival_pct <= 20 and int(now*10)%2 == 0:
            s_col = (255, 100, 100)
        else:
            s_col = s_base_col
        draw_bar(screen, WIDTH//2 - 100, 75, 200, 10, survival_pct/100.0, s_col, (30,30,50))
        draw_center(screen, f"存活率：{int(survival_pct)}%", font_xs, s_col, WIDTH//2, 95)

        # 使用全域同步後的 rhy_target_y，不再於此進行區域定義
        # rhy_target_y = int(HEIGHT * 0.83) 
        lane_x = [WIDTH//2 - 120, WIDTH//2 - 40, WIDTH//2 + 40, WIDTH//2 + 120]
        keys_pressed = pygame.key.get_pressed()
        lane_pressed = [
            keys_pressed[pygame.K_LEFT] or keys_pressed[pygame.K_a],
            keys_pressed[pygame.K_DOWN] or keys_pressed[pygame.K_s],
            keys_pressed[pygame.K_UP]   or keys_pressed[pygame.K_w],
            keys_pressed[pygame.K_RIGHT]or keys_pressed[pygame.K_d]
        ]
        
        # UI 基本渲染：繪製 4 條軌道
        for i, x in enumerate(lane_x):
            # 軌道亮起背景 (隨 Combo 變色)
            base_a = 160 if lane_pressed[i] else 90
            if c_lv >= 3: bg_col = (120, 90, 20, base_a) if lane_pressed[i] else (60, 45, 15, base_a)
            elif c_lv >= 2: bg_col = (20, 100, 130, base_a) if lane_pressed[i] else (10, 50, 70, base_a)
            else: bg_col = (40, 40, 70, base_a) if lane_pressed[i] else (20, 20, 40, 100)

            # [優化] 軌道背景 Surface 快取（最多 6 種色彩組合）
            lane_bg_key = (HEIGHT, bg_col)
            if lane_bg_key not in _lane_glow_cache:
                _s = pygame.Surface((70, HEIGHT-140), pygame.SRCALPHA)
                _s.fill(bg_col)
                _lane_glow_cache[lane_bg_key] = _s
            screen.blit(_lane_glow_cache[lane_bg_key], (x - 35, 80))
            pygame.draw.line(screen, (80,80,120), (x, 80), (x, HEIGHT-60), 1)
            # 判定圈閃爍反饋 (隨脈衝縮放)
            pulse_size = int(32 + visual_pulse * 4)

            # [優化] 外發光 Surface 快取（pulse_size 5 種×是否按下 2 種 = 10 種）
            glow_key = (pulse_size, lane_pressed[i])
            if glow_key not in _lane_glow_cache:
                _gs = pygame.Surface((pulse_size*3, pulse_size*3), pygame.SRCALPHA)
                _gc = (255, 255, 255, 180) if lane_pressed[i] else (255, 255, 200, 100)
                pygame.draw.circle(_gs, _gc, (pulse_size*3//2, pulse_size*3//2), pulse_size+5, 3)
                _lane_glow_cache[glow_key] = _gs
            screen.blit(_lane_glow_cache[glow_key], (x - pulse_size*3//2, rhy_target_y - pulse_size*3//2))

            pygame.draw.circle(screen, WHITE if lane_pressed[i] else YELLOW, (x, rhy_target_y), pulse_size, 4 if lane_pressed[i] else 2)

            # [優化] 軌道內發光漸層快取（按下時）
            if lane_pressed[i]:
                glow_h = rhy_target_y - 80
                lg_key = (glow_h, rhy_advanced)
                if lg_key not in _lane_glow_cache:
                    _lg = pygame.Surface((70, glow_h), pygame.SRCALPHA)
                    _g_col = YELLOW if not rhy_advanced else RED
                    for h in range(glow_h):
                        _a = int(100 * (h / glow_h))
                        pygame.draw.line(_lg, (*_g_col, _a), (0, h), (70, h))
                    _lane_glow_cache[lg_key] = _lg
                screen.blit(_lane_glow_cache[lg_key], (x - 35, 80))

            # 按鍵提示 (A, S, W, D)
            kl = ["A", "S", "W", "D"][i]
            draw_center(screen, kl, font_sm, WHITE if lane_pressed[i] else (150,150,180), x, rhy_target_y)

        # 顯示狀態與分數
        draw_center(screen, f"Score: {rhy_score:05d}", font_md, YELLOW, 120, 60)
        
        # 動態 Combo 文字
        cb_x, cb_y = 120, 105
        if c_lv >= 3:
            cb_c = (255, 200 + 55 * math.sin(time.time()*20), 0) # 閃爍金
            cb_x += random.randint(-4, 4); cb_y += random.randint(-4, 4) # 狂烈震動
            draw_center(screen, f"{rhy_combo} COMBO!!", font_md, cb_c, cb_x, cb_y)
        elif c_lv >= 2:
            cb_c = (0, 255, 255) # 霓虹青
            cb_x += random.randint(-2, 2); cb_y += random.randint(-2, 2) # 輕微震動
            draw_center(screen, f"{rhy_combo} Combo!", font_sm, cb_c, cb_x, cb_y)
        elif c_lv >= 1:
            draw_center(screen, f"{rhy_combo} Combo", font_sm, (150, 255, 150), cb_x, cb_y)
        else:
            draw_center(screen, f"Combo: {rhy_combo}", font_sm, (200, 200, 255), cb_x, cb_y)
            
        draw_center(screen, f"Max: {rhy_max_combo}", font_xs, (150,150,180), 120, 145)


        # 反饋文字 (Perfect/Good/Miss)
        if time.time() - rhy_msg_t < 0.6 and rhy_msg:
            mc = GREEN if rhy_msg=="Perfect!" else (CYAN if rhy_msg=="Good!" else RED)
            # 動態偏移：若正在救活，則將文字稍往上移以免遮擋 +5000
            msg_off = 90 if rhy_revive_t > 0 else 40
            fy = int(HEIGHT//2 - msg_off - (time.time() - rhy_msg_t)*30)
            draw_center(screen, rhy_msg, font_lg, mc, WIDTH//2, fy)
        
        # 5. 浮動分數特效 (Hit Score Popups)
        for fx in rhy_hits_fx[:]:
            fx['y'] -= 2 # 向上飄移
            fx['a'] -= 10 # 快速淡出
            if fx['a'] <= 0:
                rhy_hits_fx.remove(fx); continue
            draw_text_fx(screen, fx['val'], font_sm, YELLOW, fx['x'], int(fx['y']), scale=0.8, alpha=fx['a'], glow_col=(50,30,0))

        # ====== 救活連動動畫 (核心優化區) ======
        # 狀態處理
        if rhy_revive_t > 0:
            rhy_revive_t -= dt
            rhy_gauge = 0 # 置零準備
            progress = (1.8 - rhy_revive_t) / 1.8 # 0.0 -> 1.0
            
            # --- 階段 A: 準備躍起 (0.0 - 0.15) ---
            if progress < 0.15:
                # 僅繪製平躺的大叔身體
                screen.blit(body1, body1.get_rect(center=(rhy_patient_x, rhy_patient_y)))
            
            # --- 階段 B: 躍起 (Leap) (0.15 - 0.45) ---
            elif progress < 0.45:
                # 顯示大叔身體垂直上衝，並切換為 success1 (躍起姿勢)
                leap_p = (progress - 0.15) / 0.3 # 0.0 -> 1.0
                leap_y = rhy_patient_y - (leap_p * 80) # 向上躍起 80 像素
                screen.blit(succ1_i, succ1_i.get_rect(center=(rhy_patient_x, int(leap_y))))
            
            # --- 階段 C: 甦醒與慶祝 (0.45 - 0.8) ---
            elif progress < 0.8:
                # 角色落地，切換為 sw1_i (慶祝姿態)
                badge_p = min(1.0, (progress - 0.45) / 0.2)
                # 添加平滑的放大特效 (Ease-out)
                scale_f = badge_p * (2.0 - badge_p) 
                
                if scale_f > 0:
                    bw, bh = sw1_i.get_size()
                    cur_sw = pygame.transform.smoothscale(sw1_i, (int(bw * scale_f), int(bh * scale_f)))
                    screen.blit(cur_sw, cur_sw.get_rect(center=(rhy_patient_x, rhy_patient_y - 20)))
                
                # 分數文字明顯化特效 (Pop + Glow + Floating)
                txt_p = min(1.0, (progress - 0.45) / 0.35) # 使用比大叔更長的漂浮時間
                txt_scale = 1.0 + 0.5 * math.sin(txt_p * math.pi) # 爆發縮放 1.0 -> 1.5 -> 1.0
                txt_y = int(rhy_patient_y - 95 - 60 * txt_p) # 上升高度放大至 60 像素
                draw_text_fx(screen, "+5000", font_md, YELLOW, rhy_patient_x, txt_y, scale=txt_scale, glow_col=(60, 40, 0))
            
            # --- 階段 D: 漸顯躺下 (0.8 - 1.0) ---
            else:
                # 僅顯示恢復平躺的大叔身體
                fade_b = (progress - 0.8) / 0.2
                body_r = body1.get_rect(center=(rhy_patient_x, rhy_patient_y))
                body1.set_alpha(int(255 * fade_b))
                screen.blit(body1, body_r)
                body1.set_alpha(255)
        
        else:
            # --- 常態救護畫面 ---
            soul_pull = rhy_gauge / 100.0
            bt_offset = int(math.sin(time.time()*10)*2) if soul_pull >= 0.9 else 0
            body_r = body1.get_rect(center=(rhy_patient_x, rhy_patient_y + bt_offset))
            screen.blit(body1, body_r)
            
            soul_start_y, soul_target_y = 120, rhy_patient_y - 20
            soul_y = soul_start_y + (soul_target_y - soul_start_y) * soul_pull
            soul_y += math.sin(time.time() * 4) * (15 if soul_pull < 0.9 else 4)
            
            soul_r = soul1.get_rect(center=(rhy_patient_x, int(soul_y)))
            screen.blit(soul1, soul_r)
            
            # 狀態文字
            st_txt = "生命狀態：穩定 💗" if soul_pull >= 0.95 else "生命狀態：急救中..."
            st_col = GREEN if soul_pull >= 0.95 else ORANGE
            draw_center(screen, st_txt, font_sm, st_col, rhy_patient_x, rhy_patient_y + 80)
            
            # 拉回條
            draw_bar(screen, rhy_patient_x - 70, rhy_patient_y + 110, 140, 10, soul_pull, GREEN if soul_pull>=0.9 else CYAN)



        # ====== 全螢幕閃白效果 ======
        if rhy_flash_a > 0:
            overlay_surf.fill((255, 255, 255, int(rhy_flash_a)))
            screen.blit(overlay_surf, (0, 0))
            rhy_flash_a = max(0, rhy_flash_a - dt * 400) # 快速消退

        if not rhy_playing:
            draw_center(screen, "Time's up! 挑戰結束", font_lg, WHITE, WIDTH//2, HEIGHT//2-60)
            draw_center(screen, f"最終得分：{rhy_score}", font_md, YELLOW, WIDTH//2, HEIGHT//2)
            draw_center(screen, f"累計救活：{rhy_revived} 人", font_sm, GREEN, WIDTH//2, HEIGHT//2+50)
            draw_center(screen, f"最大連擊：{rhy_max_combo}", font_sm, (150,150,180), WIDTH//2, HEIGHT//2+90)
            draw_center(screen, "按 Enter 返回選單", font_xs, (150,150,180), WIDTH//2, HEIGHT-20)
        else:
            # 更新與產生音符
            rem_t = max(0, int(rhy_duration - (now - rhy_start_t)))
            draw_center(screen, f"剩餘時間: {rem_t}s", font_md, WHITE, WIDTH-120, 60)
            
            if rem_t <= 0:
                rhy_playing = False
                rhy_msg = "finish"

            # 產生音符 (間隔 = 60/BPM 秒)
            interval = 60.0 / rhy_bpm
            if now - rhy_last_gen > interval:
                # [進階功能] 決定產生音符數量：1(60%) 2(30%) 3(10%)
                count = 1
                if rhy_advanced:
                    r_val = random.random()
                    if r_val > 0.9: count = 3
                    elif r_val > 0.6: count = 2
                
                lanes = random.sample(range(4), count)
                for l in lanes:
                    rhy_notes.append({'y': -40, 'hit': False, 'lane': l})
                rhy_last_gen = now

            # 繪製與移動音符
            for note in reversed(rhy_notes):
                note['y'] += rhy_speed * dt
                if not note['hit']:
                    nx = lane_x[note.get('lane', 0)]
                    # 增強型音符渲染：發光核心
                    r_base = 22 + (visual_pulse * 3)
                    n_col = RED if not rhy_advanced else (255, 50, 50)
                    pygame.draw.circle(screen, n_col, (nx, int(note['y'])), r_base)
                    pygame.draw.circle(screen, (255, 150, 150), (nx, int(note['y'])), r_base * 0.7)
                    pygame.draw.circle(screen, WHITE, (nx, int(note['y'])), r_base * 0.3)
                    
                    # 加上外圈裝飾
                    pygame.draw.circle(screen, WHITE, (nx, int(note['y'])), r_base + 2, 1)
                    
                    if not rhy_advanced:
                        pygame.draw.line(screen, WHITE, (nx-10, int(note['y'])), (nx+10, int(note['y'])), 3)
                        pygame.draw.line(screen, WHITE, (nx, int(note['y']-10)), (nx, int(note['y']+10)), 3)
                    else:
                        # 進階模式音符標記
                        pygame.draw.polygon(screen, WHITE, [
                            (nx, int(note['y']-12)), (nx+10, int(note['y']+8)), (nx-10, int(note['y']+8))
                        ], 2)
                    
            # [優化] 批次移除超出畫面的音符，避免在迭代中呼叫 O(n) 的 remove()
            missed = [n for n in rhy_notes if n['y'] > HEIGHT + 40 and not n['hit']]
            if missed:
                rhy_combo = 0; rhy_msg_t = now; rhy_msg = "Miss!"
                fail_snd.play()
            rhy_notes[:] = [n for n in rhy_notes if n['y'] <= HEIGHT + 40]
        
        draw_center(screen, "按 A, S, W, D 或 方向鍵對應打擊   ESC 退回", font_xs, (80,80,110), WIDTH//2, HEIGHT-25)

    # ====== AED 模擬器 ======
    elif state == "aed_sim":
        screen.blit(emei_aed_bg_img, (0, 0)) # 變更為峨眉鄉彌勒佛場景 (全視窗展延)
        overlay_surf.fill((255, 255, 255, 50)) # 降低濾鏡強度，消除霧感並保持背景清晰度
        screen.blit(overlay_surf, (0, 0))

        # 定義圖片區域與座標 (確保與邏輯塊同步)
        chest_cx = WIDTH//2 - 180
        chest_cy = HEIGHT//2 - 80
        body_r = aed_body_s.get_rect(center=(chest_cx, chest_cy))
        aed_w, aed_h = 280, 280
        aed_x = WIDTH//2 + 80
        aed_y = max(20, HEIGHT//2 - 240)
        drawer_r = pygame.Rect(aed_x, aed_y + aed_h + 10, aed_w, HEIGHT - (aed_y + aed_h + 30))

        # 1. 先繪製精緻患者軀幹 (胸部圖) 以作為底層
        screen.blit(aed_body_s, body_r)

        # === 繪製上面那層的大叔 (跳起來才不會被胸圖蓋住) ===
        if aed_sub_state == "COMPLETE":
            # 電擊成功，大叔跳起 -> 站立
            if aed_elapsed < 2.0:
                # 0~2秒：大叔連續躍起 3 次 (3次半波)
                jump_offset = -abs(math.sin(aed_elapsed * math.pi * 1.5)) * 100
                sj_r = succ1_i.get_rect(centerx=chest_cx, bottom=HEIGHT - 10 + jump_offset)
                screen.blit(succ1_i, sj_r)
            else:
                # 2秒後：使用站立圖 (sw1_i)，穩定站立以供結算
                st_r = sw1_i.get_rect(centerx=chest_cx, bottom=HEIGHT - 10)
                screen.blit(sw1_i, st_r)
                
            # 將慶祝文字移至胸圖更高的上方 (超過頭部)，並將特殊符號替換為相容的 ★
            draw_center(screen, "★ 完美急救！患者已恢復心率！ ★", font_md, RED, chest_cx, body_r.top - 40)
        else:
            # 躺平的大叔放置在畫面最底部，繪製於胸圖之上
            b1_r = body1.get_rect(centerx=chest_cx, bottom=HEIGHT - 10)
            screen.blit(body1, b1_r)

        # --- 拉開上衣 (EXPOSE) ---
        if not aed_shirt_gone:
            shirt_col = (200, 200, 220)
            pygame.draw.rect(screen, shirt_col, aed_shirt_rect, border_radius=12)
            pygame.draw.rect(screen, (100,100,120), aed_shirt_rect, 2, border_radius=12)
            # 將文字分為兩行顯示，排版在方塊內更置中
            draw_center(screen, "▶ 拖曳拉開", font_msg, BLACK, aed_shirt_rect.centerx, aed_shirt_rect.centery - 18)
            draw_center(screen, "患者上衣", font_msg, BLACK, aed_shirt_rect.centerx, aed_shirt_rect.centery + 18)

        # 2. 已放置貼片
        if aed_shirt_gone:
            for p in aed_pads:
                if p["placed"]:
                    draw_rrect(screen, (240,240,250), (p["pos"][0], p["pos"][1], p["w"], p["h"]), 8, 2, (100,100,200))
                    draw_center(screen, "PAD", font_msg, BLACK, p["pos"][0]+p["w"]//2, p["pos"][1]+p["h"]//2)
                    # 纜線連結 (至插槽或插頭) 原本的已被移至後期繪圖！(註：請勿重複繪製)

        # 3. 工具箱 & 插頭 (在右側) - 新版白底樣式
        draw_rrect(screen, (245,245,250,220), drawer_r, 12, 2, (180,180,200))
        # 文字加大加粗並使用深黑色
        draw_center(screen, "救護器材箱", font_msg, BLACK, drawer_r.centerx, drawer_r.y + 25)
        
        if aed_sub_state in ("PLUG", "PADS") or aed_plugged:
            plug_col = YELLOW if not aed_plugged else GREEN
            p_rect = pygame.Rect(aed_plug_pos[0], aed_plug_pos[1], 40, 40)
            draw_rrect(screen, plug_col, p_rect, 6, 2, DARK)
            draw_center(screen, "🔌", font_msg, BLACK, p_rect.centerx, p_rect.centery)

        if aed_sub_state == "PADS":
            for p in aed_pads:
                if not p["placed"] and not p["dragging"]:
                    draw_rrect(screen, WHITE, (p["pos"][0], p["pos"][1], p["w"], p["h"]), 8, 2, BLACK)
                    draw_center(screen, "PAD", font_sm, BLACK, p["pos"][0]+p["w"]//2, p["pos"][1]+p["h"]//2)

        # 4. 繪製精緻 AED 主機 (圖片)
        screen.blit(aed_ui_s, aed_ui_rect)
        
        # 覆蓋邏輯：顯示遮蓋層提示目前狀態，並作為點擊回饋框
        if aed_sub_state == "OFF":
            s_a = int(127 + 127 * math.sin(time.time()*5))
            pygame.draw.circle(screen, (50,255,50,max(0, s_a)), aed_btn_pwr.center, 38, 4)

        if aed_sub_state == "SHOCK_READY":
            s_a = int(127 + 127 * math.sin(time.time()*8))
            pygame.draw.circle(screen, (255,80,20,max(0, s_a)), aed_btn_shk.center, 42, 5)

        if aed_sub_state == "PLUG" and not aed_plugged:
            s_a = int(127 + 127 * math.sin(time.time()*5))
            pygame.draw.circle(screen, (255,255,50,max(0, s_a)), aed_socket_rect.center, 28, 4)

        # 5. ECG 分析動畫 (在 AED 圖片附帶的黑色螢幕區域繪製)
        if aed_sub_state == "ANALYZING":
            # 畫面中央的黑色螢幕區，將波長拉高避開底下 72BPM 說明文字
            ecg_r = pygame.Rect(aed_ui_rect.x + 40, aed_ui_rect.y + 110, 110, 25)
            pygame.draw.line(screen, (20,80,20), (ecg_r.left, ecg_r.centery), (ecg_r.right, ecg_r.centery), 1)
            pts = []
            for i in range(15):
                px = ecg_r.x + (i*8)
                py = ecg_r.centery + math.sin(time.time()*15 + i)*10 + (random.randint(-2,2) if i%3==0 else 0)
                pts.append((px, py))
            if len(pts) >= 2: pygame.draw.lines(screen, (50, 255, 50), False, pts, 2)

            
        # --- 在主機上層繪製纜線 (確保插槽與主機不遮擋線材) ---
        if aed_shirt_gone:
            for i, p in enumerate(aed_pads):
                if p["placed"]:
                    # 電線顏色變更為黑色，更清晰明顯
                    pygame.draw.line(screen, BLACK, (p["pos"][0]+p["w"]//2, p["pos"][1]+p["h"]//2), (aed_plug_pos[0]+20, aed_plug_pos[1]+20), 4)


        # 6. 頂部訊息 (白底樣式 - 動態寬度防溢出)
        msg_surf = font_msg.render(aed_msg, True, BLACK)
        box_w = msg_surf.get_width() + 60
        box_h = msg_surf.get_height() + 20
        box_x = WIDTH//2 - box_w//2
        box_y = 20
        draw_rrect(screen, (240,240,245,240), (box_x, box_y, box_w, box_h), 15, 2, (180,180,200))
        draw_center(screen, aed_msg, font_msg, BLACK, WIDTH//2, box_y + box_h//2)

        # 7. 重置 / 重新操作按鈕 (在 AED 主機上方)
        aed_rst_rect = pygame.Rect(aed_ui_rect.centerx - 65, aed_ui_rect.top - 100, 130, 45)
        mx, my = pygame.mouse.get_pos()
        rst_col = (200, 50, 50) if aed_rst_rect.collidepoint(mx, my) else (150, 50, 50)
        draw_rrect(screen, rst_col, aed_rst_rect, 10, 2, (100, 20, 20))
        draw_center(screen, "↺ 重新操作", font_sm, WHITE, aed_rst_rect.centerx, aed_rst_rect.centery)

        # 最上層拖曳物件
        if aed_shirt_drag:
            draw_rrect(screen, (220,220,230), aed_shirt_rect, 10, 2, (100,100,120))
        if aed_plug_drag:
            draw_rrect(screen, YELLOW, (aed_plug_pos[0], aed_plug_pos[1], 40, 40), 6, 2, DARK)
            draw_center(screen, "🔌", font_msg, BLACK, aed_plug_pos[0]+20, aed_plug_pos[1]+20)
        for p in aed_pads:
            if p["dragging"]:
                draw_rrect(screen, YELLOW, (p["pos"][0], p["pos"][1], p["w"], p["h"]), 8, 3, DARK)
                draw_center(screen, "PAD", font_msg, BLACK, p["pos"][0]+p["w"]//2, p["pos"][1]+p["h"]//2)

        draw_center(screen, "ESC 返回選單   依據圖片指示完成操作", font_xs, (120,120,120), WIDTH//2, HEIGHT-20)

    # ====== 遊戲主體 + 結算 ======
    elif state in ("play","finish"):
        screen.blit(bg, (0,0))
        
        # --- 存活率 HUD (全模式通用) ---
        s_col = GREEN if survival_pct > 60 else (ORANGE if survival_pct > 20 else RED)
        draw_bar(screen, WIDTH//2 - 100, 15, 200, 10, survival_pct/100.0, s_col, (30,30,50))
        draw_center(screen, f"生存率：{int(survival_pct)}%", font_xs, s_col, WIDTH//2, 35)

        # --- P1 角色繪製 ---
        if play_mode=="rounds" and rc1>=round_goal:
            if p1_rt is None: p1_rt=time.time()
            screen.blit(sw1_i if time.time()-p1_rt>=2 else succ1_i,
                        sw1r  if time.time()-p1_rt>=2 else sc1r)
        elif ok1:
            screen.blit(succ1_i, sc1r)
        else:
            screen.blit(body1, b1r)
            screen.blit(soul1, s1r)

        # --- P2 角色繪製（雙打）---
        if game_mode == "dual":
            if play_mode=="rounds" and rc2>=round_goal:
                if p2_rt is None: p2_rt=time.time()
                screen.blit(sw2_i if time.time()-p2_rt>=2 else succ2_i,
                            sw2r  if time.time()-p2_rt>=2 else sc2r)
            elif ok2:
                screen.blit(succ2_i, sc2r)
            else:
                screen.blit(body2, b2r)
                screen.blit(soul2, s2r)

        # --- P1 HUD 面板 ---
        pygame.draw.rect(screen, (18,18,38), (8,8,230,130), border_radius=10)
        pygame.draw.rect(screen, (55,55,80), (8,8,230,130), 2, border_radius=10)
        if play_mode == "time":
            rem = max(0, int(time_lim-(now-start_t)))
            tc_ = YELLOW if rem>10 else RED
            screen.blit(font_md.render(f"剩餘: {rem}s", True, tc_), (18,14))
            if rem<=0 and state=="play":
                finish_t = time.time(); state="finish"
        else:
            screen.blit(font_sm.render(f"目標: {round_goal}局", True, CYAN), (18,14))

        p1_bpm_col = WHITE
        if len(tt1)>=2:
            b1v=int(calc_bpm(tt1))   # [優化] 改用 calc_bpm()
            p1_bpm_col = GREEN if BPM_MIN<=b1v<=BPM_MAX else RED
            screen.blit(font_sm.render(f"大叔BPM: {b1v}", True, p1_bpm_col), (18,48))
        screen.blit(font_sm.render(f"大叔救活: {rc1}", True, p1_bpm_col), (18,76))
        draw_bar(screen, 18, 108, 200, 12, tc1/MAX_TAPS, GREEN, (35,35,60))

        # --- P2 HUD 面板（雙打）---
        if game_mode == "dual":
            pygame.draw.rect(screen, (18,18,38), (WIDTH-238,8,230,130), border_radius=10)
            pygame.draw.rect(screen, (55,55,80), (WIDTH-238,8,230,130), 2, border_radius=10)
            p2_bpm_col = WHITE
            if len(tt2)>=2:
                b2v=int(calc_bpm(tt2))   # [優化] 改用 calc_bpm()
                p2_bpm_col = GREEN if BPM_MIN<=b2v<=BPM_MAX else RED
                screen.blit(font_sm.render(f"大嬸BPM: {b2v}", True, p2_bpm_col), (WIDTH-228,14))
            screen.blit(font_sm.render(f"大嬸救活: {rc2}", True, p2_bpm_col), (WIDTH-228,48))
            draw_bar(screen, WIDTH-228, 80, 200, 12, tc2/MAX_TAPS, CYAN, (35,35,60))

        # --- AED 提示（使用預先縮放圖示）---
        ai_h = aed_icon_s.get_height()
        if pd1:
            t1=font_sm.render("大叔AED → 空白鍵 電擊", True, RED)
            tw=aed_icon_s.get_width()+8+t1.get_width()
            ax=(WIDTH-tw)//2
            screen.blit(aed_icon_s,(ax,145)); screen.blit(t1,(ax+aed_icon_s.get_width()+8,152))
        if game_mode=="dual" and pd2:
            t2=font_sm.render("大嬸AED → 數字0 電擊", True, ORANGE)
            tw=aed_icon_s.get_width()+8+t2.get_width()
            ax=(WIDTH-tw)//2
            screen.blit(aed_icon_s,(ax,192)); screen.blit(t2,(ax+aed_icon_s.get_width()+8,199))

        # --- 計分邏輯 ---
        if not ok1 and tc1>=MAX_TAPS:
            succ_snd.play(); rc1+=1
            if play_mode=="rounds": p1_rt=time.time()
            if play_mode!="rounds" or rc1<round_goal: ok1=True

        if game_mode=="dual" and not ok2 and tc2>=MAX_TAPS:
            succ_snd.play(); rc2+=1
            if play_mode=="rounds": p2_rt=time.time()
            if play_mode!="rounds" or rc2<round_goal: ok2=True

        # --- 結束條件 ---
        if play_mode=="rounds":
            if rc1>=round_goal and not ok1: ok1=True
            if game_mode=="dual":
                if rc2>=round_goal and not ok2: ok2=True
                if rc1>=round_goal and rc2>=round_goal and finish_t is None:
                    finish_t=time.time(); state="finish"
                    # 在雙打中，目前不存入排行榜，僅單人模式錄入
            else:
                if rc1>=round_goal and finish_t is None:
                    finish_t=time.time(); state="finish"
                    # 排行榜偵測
                    load_l()
                    s_ = rhy_score if game_mode=="rhythm" else rc1*1000
                    if len(l_data) < 10 or s_ > l_data[-1]['score']:
                        is_new_record = True

        # --- 結算畫面 ---
        if state == "finish":
            overlay_surf.fill((0,0,18,185)); screen.blit(overlay_surf,(0,0))   # [優化] 複用

            elapsed_f = now - finish_t if finish_t else 0
            r_color   = GREEN
            score_txt = ""

            if play_mode == "time":
                if game_mode == "dual":
                    score_txt = f"大叔 {rc1} 比 {rc2} 大嬸"
                    if rc1>rc2:   res_txt="大叔救者 獲勝！"; r_color=GREEN
                    elif rc2>rc1: res_txt="大嬸救者 獲勝！"; r_color=CYAN
                    else:         res_txt="平手！";           r_color=YELLOW
                    if not rsnd_played:
                        (tie_snd if rc1==rc2 else succ_snd).play()
                        rsnd_played=True
                else:
                    res_txt=f"共救活 {rc1} 人！"; r_color=GREEN
                    score_txt=f"時間到！"
                    if not rsnd_played: succ_snd.play(); rsnd_played=True
            else:  # rounds
                if game_mode == "dual":
                    if p1_rt and p2_rt:
                        if p1_rt<p2_rt:   res_txt="大叔救者 獲勝！"; r_color=GREEN
                        elif p2_rt<p1_rt: res_txt="大嬸救者 獲勝！"; r_color=CYAN
                        else:             res_txt="平手！";           r_color=YELLOW
                    elif p1_rt: res_txt="大叔救者 獲勝！"; r_color=GREEN
                    elif p2_rt: res_txt="大嬸救者 獲勝！"; r_color=CYAN
                    else:       res_txt="尚未完成";         r_color=RED
                    if not rsnd_played:
                        (tie_snd if (p1_rt and p2_rt and abs(p1_rt-p2_rt)<0.01) else succ_snd).play()
                        rsnd_played=True
                else:
                    res_txt=f"完成！救活 {rc1} 人！"; r_color=GREEN
                    if not rsnd_played: succ_snd.play(); rsnd_played=True

            panel = pygame.Rect(WIDTH//2-260, HEIGHT//2-110, 520, 220)
            draw_rrect(screen, (18,18,48), panel, 18, 2, r_color)
            draw_center(screen, "🏁 結算", font_sm, (140,140,180), WIDTH//2, HEIGHT//2-82)
            draw_center(screen, res_txt, font_md, r_color, WIDTH//2, HEIGHT//2-38)
            if score_txt:
                draw_center(screen, score_txt, font_sm, WHITE, WIDTH//2, HEIGHT//2+8)

            if elapsed_f >= MIN_FINISH and int(anim_t*2)%2==0:
                if is_new_record:
                    draw_center(screen, "NEW RECORD! 請按 Enter 輸入大名", font_sm, YELLOW, WIDTH//2, HEIGHT-60)
                else: draw_center(screen, "任意鍵回選單", font_sm, WHITE, WIDTH//2, HEIGHT//2+62)

        # ====== 名稱輸入畫面 ======
        elif state == "name_input":
            screen.blit(menu_bg_img, (0,0))
            overlay_surf.fill((0,0,0,180)); screen.blit(overlay_surf,(0,0))   # [優化] 複用
            draw_center(screen, "新紀錄達成！請輸入代號", font_md, YELLOW, WIDTH//2, 120)
            draw_center(screen, "(限英文與數字 8 碼)", font_xs, WHITE, WIDTH//2, 160)
            pygame.draw.rect(screen, (50,50,80), (WIDTH//2-150, 200, 300, 60), border_radius=10)
            pygame.draw.rect(screen, YELLOW, (WIDTH//2-150, 200, 300, 60), 3, border_radius=10)
            draw_center(screen, p_name + ("_" if int(time.time()*2)%2 else ""), font_md, WHITE, WIDTH//2, 230)
            draw_center(screen, "按 Enter 確認存檔", font_sm, CYAN, WIDTH//2, 300)

        # ====== 排行榜畫面 ======
        elif state == "leaderboard":
            screen.blit(menu_bg_img, (0,0))
            overlay_surf.fill((10,10,30,220)); screen.blit(overlay_surf,(0,0))   # [優化] 複用
            draw_center(screen, "🏆 SoulPress 救護英雄榜 🏆", font_md, YELLOW, WIDTH//2, 50)
            for i, d in enumerate(l_data):
                y = 110 + i * 32
                c = GREEN if i==0 else (CYAN if i<3 else WHITE)
                row = f"{i+1:2}. {d['name']:8} | Score: {d['score']:6} | Saved: {d['revived']}"
                draw_center(screen, row, font_sm, c, WIDTH//2, y)
            if not l_data:
                draw_center(screen, "尚無紀錄，快去救人吧！", font_sm, (150,150,180), WIDTH//2, HEIGHT//2)
            draw_center(screen, "按 Enter 或 Space 返回主選單", font_xs, (100,100,130), WIDTH//2, HEIGHT-30)

    # ==========================
    # 確保非 AED 模擬模式時游標恢復原本箭頭
    if state != "aed_sim":
        pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_ARROW)

    # === 渲染粒子與震動應用 ===
    for p in particles:
        p.draw(screen)

    # 取得震動偏移 (若有)
    sx, sy = get_shake()
    if sx != 0 or sy != 0:
        # [優化] 複用預分配的 temp_screen，避免每幀呼叫 screen.copy() 擷起完整 Surface
        temp_screen.blit(screen, (0, 0))
        screen.fill(BLACK)
        screen.blit(temp_screen, (sx, sy))

    pygame.display.flip()

pygame.quit()
sys.exit()
