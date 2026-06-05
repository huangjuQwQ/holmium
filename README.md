![](https://i.imgs.ovh/2026/06/06/5705ea7d63f5f8dc56dffc068852fd4c.png)
# 💾 AstrBot Memory Optimizer-Holmium

[![Version](https://img.shields.io/badge/version-1.0.5-blue.svg)](https://github.com/huangjuQwQ/astrbot_plugin_holmium/releases/tag/v1.0.5)
[![AstrBot](https://img.shields.io/badge/AstrBot-%3E%3D4.0-green.svg)](https://github.com/Soulter/AstrBot)
[![License](https://img.shields.io/badge/license-MIT-orange.svg)](https://opensource.org/licenses/MIT)
[![Author](https://img.shields.io/badge/author-huangjuQwQ-blue)](https://github.com/huangjuQwQ)

一个专注于降低 AstrBot 内存与 CPU 消耗的性能优化插件。**所有功能默认关闭**，你可按需在 Web 面板中开启，安全无副作用。

---

## ✨ 核心功能

| 类别 | 功能 | 说明 |
|------|------|------|
| 🔧 GC 优化 | 分代阈值调整 + 定时回收 | 减少 Python 垃圾回收的全堆扫描频率，降低 CPU 与内存抖动 |
| ⚙️ CPU 优化 | 限制 asyncio 默认线程池大小 | 减少过多线程导致的上下文切换开销，提升整体效率 |
| 🧹 会话与队列 | 清理不活跃会话 + 限制事件队列长度 | 防止会话积压和队列无限增长导致 OOM |
| 🔌 其他插件优化 | 调用第三方插件的性能接口 | 通过约定方法让其他插件自主清理缓存、释放资源 |
| 🎮 手动命令 | `/重载优化配置`、`/优化其他插件`、`/手动垃圾回收` | 无需重启即可重载配置、手动触发优化或垃圾回收 |

---

## 📁 文件结构

```

data/plugins/astrbot_plugin_holmium/
├── 📄 metadata.yaml          # 插件元信息（名称、版本、作者等）
├── 📄 init.py            # 插件入口，导出主类
├── 📄 main.py                # 核心逻辑（GC、线程池限制、调度、命令）
├── 📄 config.json            # 默认配置（所有功能默认关闭）
└── 📄 _conf_schema.json      # Web 面板配置 UI 定义（分组、滑块、下拉选项）

```

---

## 🚀 快速开始

1. **将整个 `astrbot_plugin_holmium` 文件夹放入** `AstrBot/data/plugins/` 目录。
2. **重启 AstrBot**（或执行“重新加载插件”）。
3. 打开 Web 管理面板 → 插件配置 → `astrbot_plugin_holmium`，按需开启各项优化。
4. 在聊天中发送 `/手动垃圾回收` 验证插件是否正常工作。

> ⚠️ 所有优化默认关闭，请确认理解每项作用后再开启。

---

## 🔌 如何让其他插件支持优化？

本插件提供了一个**可选的优化调用链**。如果你希望某个插件能够响应内存优化请求，只需在该插件的 `Star` 子类中实现以下方法：

```python
def optimize_performance(self, level: str = "medium", caller: str = ""):
    """
    根据调用者传入的级别清理内部缓存、释放临时资源。
    
    :param level: 优化级别，可选值：
        - "light"        : 轻度清理（仅清理易失缓存）
        - "medium"       : 中等清理（推荐，清理大部分可重建数据）
        - "full"         : 彻底清理（可能影响响应速度，需重建）
        - "extreme"      : 激进清理（谨慎使用，会丢弃大量缓存）
        - "conservative" : 保守清理（仅重置临时状态）
    :param caller: 调用者名称（本插件传入 "astrbot_plugin_holmium"）
    """
    if level == "light":
        # 清理临时缓存字典
        self._temp_cache.clear()
    elif level == "medium":
        # 清理 + 重置部分统计
        self._cache.clear()
        self._counter = 0
    elif level == "full":
        # 完全重建内部数据结构
        self._reinitialize()
    # ... 按需实现
```

示例：让一个假想的 weather_plugin 支持优化

```python
from astrbot.api.star import Star

class WeatherPlugin(Star):
    def __init__(self, context):
        self._city_cache = {}        # 缓存城市天气数据
        self._request_history = []   # 历史请求记录
    
    def optimize_performance(self, level: str = "medium", caller: str = ""):
        if level == "light":
            # 只清除超过1小时的缓存
            self._clean_old_cache(hours=1)
        elif level == "medium":
            self._city_cache.clear()
            self._request_history.clear()
        elif level == "full":
            self._city_cache.clear()
            self._request_history.clear()
            self._reset_connection_pool()
```

📌 无需修改本插件，本插件会自动扫描所有已加载插件，若存在 optimize_performance 方法则调用之。没有该方法的插件完全不受影响。

---

🧪 手动命令

命令 作用
/重载优化配置 重新加载 config.json，热生效
/优化其他插件 立即调用所有支持优化接口的插件
/手动垃圾回收 强制执行一次 Python 垃圾回收

---

⚙️ 配置项一览

分组 配置项 类型 默认值 说明
GC 优化 启用 GC 优化 bool false 开启后调整阈值并定时回收
 第0代阈值（新生代） int 700 超过此数量触发新生代回收
 第1代阈值（幸存代） int 10 超过此数量触发幸存代回收
 第2代阈值（老年代） int 10 超过此数量触发老年代回收
 主动 GC 间隔（秒） int 300 定时调用 gc.collect() 的间隔
CPU 优化 启用 CPU 优化 bool false 开启后限制 asyncio 默认线程池大小
 最大工作线程数 int 4 线程池大小上限，推荐设为 CPU 核心数
会话与队列 清理不活跃会话（天） int 0 超过天数未活动则清理，0=禁用
 事件队列最大长度 int 1000 防止队列积压
其他插件优化 总开关 bool false 关闭后完全不调用其他插件
 启用调用 bool false 仅当总开关开启时生效
 优化级别 string medium light/medium/full/extreme/conservative
 自动调用间隔（小时） int 0 0=不自动调用
 启动时立即调用 bool false 插件加载后立即执行一次

---

📋 更新日志

v1.0.5 (2026-06-06)

· 新增 Web 面板分组折叠支持（GC 优化、CPU 优化、会话与队列、其他插件优化）
· 新增 对其他插件的性能优化接口（optimize_performance 方法）
· 新增 手动命令 /重载优化配置、/优化其他插件、/手动垃圾回收
· 新增 CPU 优化：限制 asyncio 默认线程池大小，减少上下文切换
· 优化 优化级别的枚举选项说明
· 修复 兼容 AstrBot v4.25.2 的配置加载机制（使用 items 而非 properties）
· 安全 所有功能默认关闭，避免误开启导致问题

---

🤝 贡献与反馈

欢迎提交 Issue 或 PR 改进本插件。如果你在使用中遇到任何问题，请附上 AstrBot 日志。

---

Enjoy a lighter AstrBot! 🚀
![](https://i.imgs.ovh/2026/06/06/10c0b52941204da0afc7bf018f101344.png)
```
