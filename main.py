import json
import gc
import asyncio
import os
import logging
from datetime import datetime, timedelta
from astrbot.api.star import Context, Star, register
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api import logger

@register("astrbot_plugin_holmium", "Optimizer", "一个内存优化插件", "1.0.5", "https://github.com/your-repo")
class MemoryOptimizer(Star):
    def __init__(self, context: Context) -> None:
        super().__init__(context)
        self.config = self._load_config()
        self._optimize_task = None
        self._apply_initial_settings()

    def _load_config(self):
        config_path = os.path.join(os.path.dirname(__file__), "config.json")
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {
            "enable_gc_optimization": False,
            "gc_threshold_gen0": 700,
            "gc_threshold_gen1": 10,
            "gc_threshold_gen2": 10,
            "gc_interval_seconds": 300,
            "enable_log_level_reduction": False,
            "log_level": "WARNING",
            "clear_unused_sessions_days": 0,
            "max_event_queue_size": 1000,
            "optimize_other_plugins": False,
            "other_plugin_optimization_enabled": False,
            "other_plugin_optimization_level": "medium",
            "other_plugin_optimization_interval_hours": 0,
            "other_plugin_optimization_call_on_startup": False
        }

    def _apply_initial_settings(self):
        if self.config.get("enable_gc_optimization", False):
            gen0 = self.config.get("gc_threshold_gen0", 700)
            gen1 = self.config.get("gc_threshold_gen1", 10)
            gen2 = self.config.get("gc_threshold_gen2", 10)
            gc.set_threshold(gen0, gen1, gen2)
            logger.info(f"[内存优化] GC阈值已设为 [{gen0}, {gen1}, {gen2}]")

        if self.config.get("enable_log_level_reduction", False):
            log_level_str = self.config.get("log_level", "WARNING").upper()
            log_level = getattr(logging, log_level_str, logging.WARNING)
            logging.getLogger().setLevel(log_level)
            logger.info(f"[内存优化] 日志级别已设为 {log_level_str}")

        try:
            from astrbot.core.event import event_manager
            if hasattr(event_manager, 'set_max_queue_size'):
                event_manager.set_max_queue_size(self.config.get("max_event_queue_size", 1000))
                logger.info(f"[内存优化] 事件队列大小限制设为 {self.config.get('max_event_queue_size')}")
        except Exception as e:
            logger.debug(f"[内存优化] 无法设置事件队列大小: {e}")

    async def _call_other_plugin_optimization(self):
        if not self.config.get("optimize_other_plugins", False):
            return
        if not self.config.get("other_plugin_optimization_enabled", False):
            return

        level = self.config.get("other_plugin_optimization_level", "medium")
        logger.info(f"[内存优化] 开始调用其他插件的性能优化方法 (级别: {level})")

        try:
            plugin_manager = self.context.get_plugin_manager()
            if plugin_manager is None:
                logger.warning("[内存优化] 无法获取插件管理器，跳过优化调用")
                return

            all_plugins = plugin_manager.get_all_plugins()
            count = 0
            for plugin in all_plugins:
                if plugin == self:
                    continue
                if hasattr(plugin, "optimize_performance") and callable(plugin.optimize_performance):
                    try:
                        if asyncio.iscoroutinefunction(plugin.optimize_performance):
                            await plugin.optimize_performance(level=level, caller="astrbot_plugin_holmium")
                        else:
                            plugin.optimize_performance(level=level, caller="astrbot_plugin_holmium")
                        count += 1
                        logger.debug(f"[内存优化] 已调用 {plugin.__class__.__name__}.optimize_performance()")
                    except Exception as e:
                        logger.error(f"[内存优化] 调用 {plugin.__class__.__name__} 优化方法时出错: {e}")
            logger.info(f"[内存优化] 共调用 {count} 个插件的优化方法")
        except Exception as e:
            logger.error(f"[内存优化] 扫描插件失败: {e}")

    async def _periodic_optimize(self):
        while True:
            try:
                interval = self.config.get("gc_interval_seconds", 300)
                await asyncio.sleep(interval)

                new_config = self._load_config()
                if new_config != self.config:
                    self.config = new_config
                    self._apply_initial_settings()
                    logger.info("[内存优化] 配置已热更新")

                if self.config.get("enable_gc_optimization", False):
                    collected = gc.collect()
                    if collected > 0:
                        logger.debug(f"[内存优化] 主动 GC 回收了 {collected} 个对象")

                days = self.config.get("clear_unused_sessions_days", 0)
                if days > 0:
                    try:
                        session_mgr = self.context.get_session_manager()
                        if session_mgr and hasattr(session_mgr, 'clear_inactive_sessions'):
                            before = datetime.now() - timedelta(days=days)
                            cleared = session_mgr.clear_inactive_sessions(before)
                            if cleared:
                                logger.info(f"[内存优化] 清除了 {cleared} 个不活跃会话")
                    except Exception:
                        pass

                interval_hours = self.config.get("other_plugin_optimization_interval_hours", 0)
                if interval_hours > 0 and self.config.get("optimize_other_plugins", False) and self.config.get("other_plugin_optimization_enabled", False):
                    if not hasattr(self, '_last_plugin_optimize_call'):
                        self._last_plugin_optimize_call = datetime.now()
                    now = datetime.now()
                    if (now - self._last_plugin_optimize_call).total_seconds() >= interval_hours * 3600:
                        await self._call_other_plugin_optimization()
                        self._last_plugin_optimize_call = now

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[内存优化] 后台任务异常: {e}")

    async def _on_start(self):
        self._optimize_task = asyncio.create_task(self._periodic_optimize())
        logger.info("[内存优化] 后台优化任务已启动")

        if self.config.get("optimize_other_plugins", False) and self.config.get("other_plugin_optimization_call_on_startup", False):
            await self._call_other_plugin_optimization()
            self._last_plugin_optimize_call = datetime.now()

    async def _on_stop(self):
        if self._optimize_task:
            self._optimize_task.cancel()
            try:
                await self._optimize_task
            except asyncio.CancelledError:
                pass
            logger.info("[内存优化] 后台优化任务已停止")

    async def terminate(self):
        await self._on_stop()

    @filter.command("重载优化配置")
    async def reload_config(self, event: AstrMessageEvent):
        self.config = self._load_config()
        self._apply_initial_settings()
        yield event.plain_result("✅ 内存优化插件配置已重载")

    @filter.command("优化其他插件")
    async def call_plugin_optimize(self, event: AstrMessageEvent):
        await self._call_other_plugin_optimization()
        yield event.plain_result("✅ 已请求所有支持优化的插件进行性能清理")

    @filter.command("手动垃圾回收")
    async def manual_gc(self, event: AstrMessageEvent):
        collected = gc.collect()
        yield event.plain_result(f"🧹 手动垃圾回收完成，回收了 {collected} 个对象")