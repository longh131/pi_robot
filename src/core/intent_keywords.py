# src/core/intent_keywords.py
# 意图分流关键词库
# 优先级顺序: SYSTEM > MOTOR > ASSISTANT > ENTERTAINMENT > QUERY > CHAT

# 系统控制
SYSTEM_KEYWORDS = {
    "SYSTEM_VOLUME_UP": ["大声点", "音量加", "调高音量", "调大音量", "升高音量", "增大声音", "增加音量"],
    "SYSTEM_VOLUME_DOWN": ["小声点", "音量减", "调低音量", "调小音量", "降低音量", "减小声音", "减少音量"],
    "SYSTEM_STOP": ["停止一切活动", "停住", "不要废话了", "关闭一切", "别动", "停止一切", "停停停"],
    "SYSTEM_STATUS": ["状态", "能量", "报告情况", "你怎么样", "身体怎么样了"]
}

# 电机控制
MOTOR_KEYWORDS = {
    "MOVE_FORWARD": ["前进", "往前走", "向前", "走", "直走", "出发", "继续前进", "继续走", "过来"],
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
    "STOP_RECORDING": ["停止录像", "结束录像", "关闭摄像头", "管理相机"],
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

# 优先级顺序列表（按优先级从高到低）
KEYWORD_PRIORITY = [
    SYSTEM_KEYWORDS,
    MOTOR_KEYWORDS,
    ASSISTANT_KEYWORDS,
    ENTERTAINMENT_KEYWORDS,
    QUERY_KEYWORDS,
]

# 意图类型分类
INTENT_CATEGORIES = {
    "SYSTEM": ["SYSTEM_VOLUME_UP", "SYSTEM_VOLUME_DOWN", "SYSTEM_STOP", "SYSTEM_STATUS"],
    "MOTOR": ["MOVE_FORWARD", "MOVE_BACKWARD", "TURN_LEFT", "TURN_RIGHT", "STOP", "SPEED_UP", "SPEED_DOWN", "FOLLOW_ME", "DANCE"],
    "ASSISTANT": ["REMINDER_SET", "REMINDER_QUERY", "REMINDER_DELETE", "ALARM_SET", "TIMER_SET"],
    "ENTERTAINMENT": ["TAKE_PHOTO", "START_RECORDING", "STOP_RECORDING", "PLAY_MUSIC", "PAUSE_MUSIC", "STOP_MUSIC", "NEXT_SONG", "PREV_SONG", "RESUME_MUSIC"],
    "QUERY": ["WEATHER_QUERY", "TIME_QUERY", "DATE_QUERY", "NEWS_QUERY"],
}

# 意图别名映射（LLM可能返回的别名 → 标准意图）
INTENT_ALIAS_MAP = {
    # 音量相关
    "INCREASE_VOLUME": "SYSTEM_VOLUME_UP",
    "DECREASE_VOLUME": "SYSTEM_VOLUME_DOWN",
    "VOLUME_UP": "SYSTEM_VOLUME_UP",
    "VOLUME_DOWN": "SYSTEM_VOLUME_DOWN",
    
    # 运动相关
    "FOLLOW_USER": "FOLLOW_ME",
    "FOLLOW": "FOLLOW_ME",
    "MOVE": "MOVE_FORWARD",
    "GO_FORWARD": "MOVE_FORWARD",
    "GO_BACKWARD": "MOVE_BACKWARD",
    "TURN": "TURN_LEFT",
    
    # 娱乐相关
    "PHOTO": "TAKE_PHOTO",
    "RECORD": "START_RECORDING",
    "MUSIC": "PLAY_MUSIC",
    "SING": "PLAY_MUSIC",
    
    # 查询相关
    "WEATHER": "WEATHER_QUERY",
    "TIME": "TIME_QUERY",
    "DATE": "DATE_QUERY",
    "NEWS": "NEWS_QUERY",
}
