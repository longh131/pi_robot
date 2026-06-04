# 小派 (Pi-Robot) 项目上下文 Prompt

## 项目概述
小派是一个基于树莓派的智能机器人项目，采用模块化异步驱动架构，支持离线唤醒、大模型对话、娱乐控制等功能。当前版本为 v1.0.0 (RC-1)，核心特性包括低功耗架构、流式语音识别、异步语音合成和插件系统。

## 技术栈
- **硬件平台**：Raspberry Pi (BCM2712_C0)
- **编程语言**：Python 3.11
- **核心框架**：
  - 语音唤醒：Sherpa-ONNX (离线流式唤醒)
  - 语音识别：Whisper (ASR)
  - 大语言模型：Qwen (LLM)
  - 语音合成：Qwen3-TTS (TTS)
  - Web服务：Flask + Flask-SocketIO (远程控制)
  - 摄像头：picamera2 (libcamera)
  - 电机控制：gpiozero + L298N 驱动板

## 已完成功能

### 1. 核心状态机
- **状态定义**：IDLE (待机)、AWAKENING (唤醒中)、LISTENING (侦听中)、THINKING (思考中)、SPEAKING (播报中)
- **状态流转**：
  - IDLE → AWAKENING：检测到唤醒词（不在REMOTE状态下）
  - AWAKENING → LISTENING：播放欢迎语后进入侦听
  - LISTENING → THINKING：识别到用户语音
  - THINKING → SPEAKING：生成语音回复
  - SPEAKING → LISTENING：播报完成继续侦听
  - 任意状态 → IDLE：超时（10分钟）、检测到退出词

### 2. AWAKE 状态流程
```
IDLE状态 → 检测唤醒词 (不在REMOTE状态下)
        ↓
    AWAKE状态
        ↓
    ┌────────────────────────────────────────────────────────┐
    │  循环监听语音 (awake_timeout: 10分钟超时/exit_words可退出)  │
    └────────────────────────────────────────────────────────┘
        ↓
    语音输入检测
        ↓
    ASR语音识别 → 文本
        ↓
    本地关键词匹配 (按优先级: SYSTEM > MOTOR > DEVICE > ASSISTANT > ENTERTAINMENT > QUERY > UTILITY > CHAT)
        ├─ 是 → 直接执行本地指令 (无TTS播报)
        └─ 否 → LLM处理
                    ↓
               LLM结构化输出 (JSON格式，枚举约束)
                    ↓
               {"intent": "枚举值", "params": {}}
                    ├─ 含意图枚举 → 执行对应本地指令 + LLM回答 + TTS播报
                    └─ NONE → LLM回答 + TTS播报
                    ↓
               继续监听 (或退出到IDLE)
```

**核心特性**：
- **紧急打断**：全局Event机制，可完全停止所有指令和播报，停止后仍是awake状态
- **长期记忆**：SQLite数据库存储对话历史，LLM调用时带上上下文
- **本地指令优先**：减少LLM调用，提高响应速度

### 2. 语音交互系统
- **离线唤醒**：支持自定义唤醒词（"小派同学"、"小派"、"派派"等）
- **流式识别**：实时将用户语音转化为文本
- **智能理解**：集成 LLM，支持角色设定和上下文记忆
- **打断机制**：在机器人说话过程中，检测到新语音可立即停止当前动作
- **超时退出**：唤醒后无操作超过设定时间（默认180秒）自动进入待机状态

### 3. 娱乐控制插件
- **摄像头功能**：
  - 拍照：语音指令"拍照"、"照相"、"拍张照片"触发
  - 录像：语音指令"录像"、"开始录像"开始录制，"停止录像"、"结束录像"停止录制
  - 存储：照片保存在 `data/media/photo_*.jpg`，录像保存在 `data/media/video_*.h264`
- **音乐播放**：
  - 播放：语音指令"播放音乐"、"放歌"播放音乐
  - 控制：支持暂停、停止、上一首、下一首
  - 随机播放：自动随机选择音乐播放

### 4. 运动控制插件
- **前进/后退**：语音指令控制机器人移动
- **左转/右转**：语音指令控制机器人转向
- **停止**：语音指令"停止移动"、"停止走动"停止电机
- **避障功能**：集成超声波传感器，自动避障

### 5. 意图识别系统
- **本地指令优先**：常用控制指令（拍照、录像、音乐播放等）直接本地识别执行，无需调用 LLM
- **紧急停止词**：支持配置全局紧急停止词（"停止"、"停"、"住手"等），可立即停止所有活动
- **关键词配置**：所有关键词统一配置在 `config/intent_keywords.py`

### 6. 插件系统
- **LED 插件**：状态指示灯控制（GPIO 17）
- **电机插件**：机器人运动控制
- **娱乐插件**：摄像头和音乐播放功能
- **跟随插件**：自动跟随功能
- **跳舞插件**：预设舞蹈动作

## 关键技术决策

### 1. 性能优化
- **CPU 占用率优化**：引入"呼吸循环"机制，将轮询频率限制在 100Hz 左右，CPU 占用从 120% 降至 15%~25%
- **非阻塞回调**：采用 sounddevice 异步回调捕获音频，确保在休眠期间不会丢失任何语音片段
- **线程守护**：对话逻辑在独立守护线程运行，支持 cancel_event 紧急打断

### 2. 音频冲突处理
- **TTS 与音乐冲突**：先 TTS 播报，再执行音乐播放指令
- **本地指令流程**：本地检测到的指令直接执行，不进行 TTS 播报

### 3. 紧急停止逻辑
- **全局停止**：检测到"停止一切"、"停止"、"停停停"等词，立即停止所有活动
- **特定插件停止**：
  - 音乐："暂停音乐"、"停止音乐"
  - 电机："停止移动"、"停止走动"
  - 摄像头："停止录像"、"停止拍照"

### 4. 长期记忆机制
- **存储方式**：SQLite数据库 (`data/robot_memory.db`)
- **存储内容**：对话历史、用户偏好、上下文信息
- **使用方式**：每次LLM调用时带上最近N条对话历史

## AWAKE模块分步开发流程

### 阶段1：基础框架与状态流转
- 完善AWAKE状态监听循环
- 实现10分钟（"awake_timeout"配置）超时与exit_words检测
- 集成紧急打断机制 (全局Event)

### 阶段2：ASR与本地关键词匹配
- 完善流式ASR识别
- 实现按优先级的本地关键词匹配
- 本地指令直接执行 (无TTS)

### 阶段3：LLM结构化输出
- 实现LLM结构化输出 (JSON枚举)
- LLM结果意图解析
- 意图枚举执行对应指令

### 阶段4：LLM对话与长期记忆
- SQLite数据库设计
- 对话历史存储与读取
- LLM上下文集成

### 阶段5：TTS与完整流程联调
- 完善TTS播报流程
- 完整流程联调测试
- 性能优化

## 即将开发的远程控制模块

### 1. 远程控制架构
```
┌─────────────────────────────────────────────────────────────┐
│                      机器人状态机                           │
├─────────────────────────────────────────────────────────────┤
│  IDLE（待机）     ←───  可被远程控制接入                     │
│  AWAKE（唤醒）    ←───  语音交互中，拒绝远程接入              │
│  REMOTE（远程）   ←───  远程控制中，屏蔽唤醒词               │
└─────────────────────────────────────────────────────────────┘
核心原则 ：三个状态互斥，同一时间只能处于一个状态。
```

### 2. 状态流转规则
```
        语音唤醒               远程接入
       ┌─────────┐           ┌─────────┐
       ▼         │           ▼         │
    ┌──────┐     │        ┌──────┐     │
    │ IDLE │     │        │IDLE  │     │
    └──────┘     │        └──────┘     │
       │         │           │         │
       │ 唤醒    │           │ 远程接入│
       ▼         │           ▼         │
    ┌──────┐     │        ┌──────┐     │
    │AWAKE │─────┘        │REMOTE│─────┘
    └──────┘  超时/退出    └──────┘   断开连接
```

### 3. 远程控制功能
- **Web 界面**：基于 HTML5 + JavaScript 的控制界面
- **用户认证**：JWT token 认证，支持多用户管理
- **视频监控**：实时视频流传输（基于 OpenCV）
- **运动控制**：通过 Web 界面控制机器人前进、后退、左转、右转、停止
- **娱乐控制**：远程拍照、录像、播放音乐
- **状态管理**：只有在 IDLE 状态下才能进行远程控制，AWAKE 状态下拒绝远程接入，REMOTE 状态下屏蔽唤醒词检测

### 4. 远程控制组件
- **RemoteController**：远程控制协调器，管理远程控制会话和状态
- **RemoteServer**：Web 服务器，提供 HTTP 和 WebSocket 接口
- **AuthManager**：用户认证和 JWT token 生成
- **MediaManager**：视频流处理
- **ControlManager**：远程控制指令处理

### 5. 远程控制 API
- `POST /api/login`：用户登录，返回 JWT token
- `GET /api/status`：检查远程控制状态
- `POST /api/activate`：激活远程控制
- `POST /api/deactivate`：停用远程控制
- `POST /api/command`：执行远程控制指令
- `GET /api/video_feed`：获取视频流

### 6. 远程控制约束
- **状态互斥**：IDLE 状态下才能被唤醒或远程接入
- **AWAKE 拒绝远程**：语音交互中，拒绝远程连接请求
- **REMOTE 屏蔽唤醒**：远程控制中，屏蔽唤醒词检测
- **会话管理**：远程控制会话超时自动断开

## 项目目录结构
```
pi/
├── config/                    # 配置文件目录
│   ├── intent_keywords.py     # 意图关键词配置
│   └── remote_config.py     # 远程控制配置
├── data/                      # 数据目录
│   ├── robot_profile.json     # 机器人配置
│   ├── remote_auth.json      # 远程控制认证配置
│   └── media/                 # 媒体文件存储
├── src/                       # 源代码目录
│   ├── core/                  # 核心模块
│   │   ├── brain.py           # 状态机核心
│   │   ├── intent_handler.py  # 意图处理器
│   │   ├── parser.py          # 协议解析器
│   │   └── remote_controller.py  # 远程控制协调器
│   ├── plugins/               # 插件目录
│   │   ├── voice/             # 语音插件
│   │   ├── motor/             # 电机插件
│   │   ├── led/               # LED插件
│   │   ├── entertainment/     # 娱乐插件
│   │   └── remote/            # 远程控制插件
│   │       ├── server.py       # Web服务器
│   │       ├── auth.py         # 认证模块
│   │       ├── media.py        # 媒体流处理
│   │       └── control.py      # 控制指令处理
│   └── static/                # 前端静态文件
│       └── index.html         # 远程控制界面
├── models/                    # 模型文件目录
├── logs/                      # 日志目录
├── requirements.txt           # 依赖列表
├── README.md                # 项目文档
└── start_remote.py           # 远程控制启动脚本
```

## 配置文件说明

### 1. 机器人配置 (data/robot_profile.json)
```json
{
  "robot": {
    "wake_words": ["小派同学", "小派", "派派", "派同学", "xiaopai", "paipai", "你好", "小拍"],
    "exit_words": ["退出", "再见", "拜拜", "小派休息吧"],
    "emergency_stop_words": ["别说了", "闭嘴", "停止", "停", "住手", "别动", "安静", "停止一切", "停停停", "停止一切活动", "关闭一切"]
  },
  "personality": {
    "greeting": ["你好，我在听，请说吧。", "你好！有什么我可以帮你的吗？"],
    "farewell": ["再见，期待下次见面！", "好的，下次见！"],
    "system_prompt": "你是小派，一个智能机器人助手..."
  }
}
```

### 2. 意图关键词配置 (config/intent_keywords.py)
优先级顺序: SYSTEM > MOTOR > DEVICE > ASSISTANT > ENTERTAINMENT > QUERY > UTILITY > CHAT

```python
# 系统控制
SYSTEM_KEYWORDS = {
    "SYSTEM_VOLUME_UP": ["大声点", "音量加", "调高音量", "调大音量", "升高音量", "增大声音", "增加音量"],
    "SYSTEM_VOLUME_DOWN": ["小声点", "音量减", "调低音量", "调小音量", "降低音量", "减小声音", "减少音量"],
    "SYSTEM_STOP":["停止一切活动","停住","不要废话了","关闭一切","别动", "停止一切", "停停停"],
    "SYSTEM_STATUS": ["状态", "能量", "报告情况", "你怎么样", "身体怎么样了"]
}

# 电机控制
MOTOR_KEYWORDS = {
    "MOVE_FORWARD": ["前进", "往前走", "向前", "走", "直走", "出发", "继续前进", "继续走","过来"],
    "MOVE_BACKWARD": ["后退", "往后走", "向后", "退后", "倒车"],
    "TURN_LEFT": ["左转", "向左", "左拐", "转左", "往左"],
    "TURN_RIGHT": ["右转", "向右", "右拐", "转右", "往右"],
    "STOP": ["停止移动", "停止走动", "站住", "刹车"],
    "SPEED_UP": ["加速", "快点", "快一点", "加快"],
    "SPEED_DOWN": ["减速", "慢点", "慢一点", "放慢"],
    "FOLLOW_ME": ["跟着我", "跟随", "跟我走"],
    "DANCE": ["跳舞", "跳个舞", "来一段"],
}

# 助手控制
ASSISTANT_KEYWORDS = {
    "REMINDER_SET": ["提醒我", "记住", "帮我记着", "别忘了"],
    "REMINDER_QUERY": ["我的提醒", "有什么提醒", "查看提醒"],
    "REMINDER_DELETE": ["删除提醒", "取消提醒", "清除提醒"],
    "ALARM_SET": ["设个闹钟", "闹钟", "几点叫醒", "叫醒我"],
    "TIMER_SET": ["计时", "倒计时", "定时", "计时器"],
}

# 娱乐控制
ENTERTAINMENT_KEYWORDS = {
    "TAKE_PHOTO": ["拍照", "照相", "拍张照片", "照张相"],
    "START_RECORDING": ["录像", "开始录像", "录制视频"],
    "STOP_RECORDING": ["停止录像", "结束录像","关闭摄像头","管理相机"],
    "PLAY_MUSIC": ["播放音乐", "放歌", "音乐"],
    "PAUSE_MUSIC": ["暂停音乐", "暂停"],
    "STOP_MUSIC": ["停止音乐", "关音乐"],
    "NEXT_SONG": ["下一首", "下曲"],
    "PREV_SONG": ["上一首", "上曲"],
    "RESUME_MUSIC": ["继续", "继续播放", "继续音乐"]
}

# 查询类
QUERY_KEYWORDS = {
    "WEATHER_QUERY": ["天气", "温度", "多少度", "热不热", "冷不冷"],
    "TIME_QUERY": ["时间", "几点", "几点了", "现在几点"],
    "DATE_QUERY": ["日期", "几号", "今天几号", "什么日子"],
    "NEWS_QUERY": ["新闻", "有什么新闻", "头条", "热点"],
}

# LLM结构化输出意图枚举
INTENT_ENUM = [
    # SYSTEM
    "SYSTEM_VOLUME_UP", "SYSTEM_VOLUME_DOWN", "SYSTEM_STOP", "SYSTEM_STATUS",
    # MOTOR
    "MOVE_FORWARD", "MOVE_BACKWARD", "TURN_LEFT", "TURN_RIGHT", "STOP", "SPEED_UP", "SPEED_DOWN", "FOLLOW_ME", "DANCE",
    # ASSISTANT
    "REMINDER_SET", "REMINDER_QUERY", "REMINDER_DELETE", "ALARM_SET", "TIMER_SET",
    # ENTERTAINMENT
    "TAKE_PHOTO", "START_RECORDING", "STOP_RECORDING", "PLAY_MUSIC", "PAUSE_MUSIC", "STOP_MUSIC", "NEXT_SONG", "PREV_SONG", "RESUME_MUSIC",
    # QUERY
    "WEATHER_QUERY", "TIME_QUERY", "DATE_QUERY", "NEWS_QUERY",
    # 其他
    "EXIT", "NONE"
]
```

### 3. 远程控制配置 (config/remote_config.py)
```python
REMOTE_CONFIG = {
    "host": "0.0.0.0",
    "port": 8080,
    "auth_secret": "your-secret-key-here",
    "token_expiry": 3600,
    "video_width": 640,
    "video_height": 480,
    "video_fps": 30
}
```

### 4. 远程控制认证 (data/remote_auth.json)
```json
{
  "admin": {
    "username": "admin",
    "password": "admin123",
    "role": "admin"
  }
}
```

## 已知问题和注意事项

### 1. 硬件依赖
- **摄像头**：依赖 libcamera，需要确保系统已正确安装 `sudo apt install libcamera-tools python3-libcamera`
- **音频设备**：音乐播放与 TTS 播报使用同一音频设备，需要注意时序控制

### 2. 性能问题
- **CPU 占用**：已通过"呼吸循环"机制优化，CPU 占用率稳定在 15%~25%
- **PipeWire 错误**：已彻底解决 PipeWire xrun 错误导致的死机问题

### 3. 远程控制注意事项
- **状态互斥**：IDLE 状态下才能被唤醒或远程接入，确保状态一致性
- **安全认证**：生产环境建议使用更强的哈希算法（如 bcrypt）存储密码
- **网络配置**：确保树莓派网络连接正常，可访问远程控制端口

## 下一步开发计划

### 1. 远程控制模块完善
- **用户管理**：支持多用户和角色管理
- **权限控制**：不同用户具有不同的操作权限
- **会话管理**：优化远程控制会话的超时和断开逻辑
- **日志记录**：记录远程控制操作日志

### 2. 性能优化
- **视频流优化**：降低视频流延迟和带宽占用
- **WebSocket 优化**：使用 WebSocket 替代 HTTP 轮询，提高实时性
- **缓存机制**：缓存常用指令和响应，减少延迟

### 3. 功能扩展
- **语音控制**：远程控制界面集成语音控制功能
- **预设动作**：支持预设动作序列的远程执行
- **数据可视化**：实时显示机器人状态和传感器数据

## 重要提醒
1. **代码风格**：遵循项目现有的代码风格和命名规范
2. **注释规范**：只修改明确要求修改的内容，其他内容不要动包括注释
3. **测试验证**：修改代码后必须进行测试验证
4. **文档更新**：修改功能后及时更新 README.md 文档
5. **备份习惯**：重要修改前备份相关文件

## 常用命令
```bash
# 启动机器人
source venv/bin/activate
python src/core/brain.py

# 测试摄像头
rpicam-hello

# 查看日志
tail -f logs/*.log
```
## 命名规范
类型	规范	示例
常量	全大写下划线	MOTOR_LEFT_FORWARD
变量	小写下划线	motor_speed
函数	小写下划线	move_forward()
类	驼峰大写	MotorDriver
方法	小写下划线	set_speed()
事件	全大写下划线	EVENT_WAKE
私有成员	单下划线前缀	_internal_state
特殊方法	双下划线	__init__

## 协作规则
严格按照项目阶段顺序指导，不要跳跃。
只修改我明确要求修改的文件，其他文件不要动。
一次只做一个模块，完成后等我确认再继续。
需要修改已有代码时，先说明修改内容和原因，等我确认后再执行。
生成的代码要能直接运行，包含必要的 import 和异常处理。
遵循项目现有命名规范（常量全大写，变量小写下划线，类驼峰大写）。
配置文件从 config.json 读取，密钥从 .env 读取，机器人身份从 data/robot_profile.json 读取。
添加必要注释，不要过度注释。

## 联系方式
如需继续开发此项目，请提供以上上下文信息，确保代码风格和架构的一致性。