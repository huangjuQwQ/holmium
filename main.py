import json
import gc
import asyncio
import os
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from astrbot.api.star import Context, Star, register
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api import logger

@register("astrbot_plugin_holmium", "Optimizer", "一个内存与CPU优化插件", "1.0.9", "https://github.com/huangjuQwQ/astrbot_plugin_holmium")
class MemoryOptimizer(Star):
    def __init__(self, context: Context) -> None:
        super().__init__(context)
        self.config = self._load_config()
        self._optimize_task = None
        self._original_executor = None
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
            "clear_unused_sessions_days": 0,
            "max_event_queue_size": 1000,
            "enable_cpu_optimization": False,
            "max_worker_threads": 4,
            "optimize_other_plugins": False,
            "other_plugin_optimization_enabled": False,
            "other_plugin_optimization_level": "medium",
            "other_plugin_optimization_interval_hours": 0,
            "other_plugin_optimization_call_on_startup": False
        }

    def _apply_initial_settings(self):
        # GC 优化
        if self.config.get("enable_gc_optimization", False):
            gen0 = self.config.get("gc_threshold_gen0", 700)
            gen1 = self.config.get("gc_threshold_gen1", 10)
            gen2 = self.config.get("gc_threshold_gen2", 10)
            gc.set_threshold(gen0, gen1, gen2)
            logger.info(f"[优化] GC阈值已设为 [{gen0}, {gen1}, {gen2}]")

        # CPU 优化：限制默认线程池大小
        if self.config.get("enable_cpu_optimization", False):
            max_workers = self.config.get("max_worker_threads", 4)
            self._set_thread_pool_limit(max_workers)

        # 事件队列限制
        try:
            from astrbot.core.event import event_manager
            if hasattr(event_manager, 'set_max_queue_size'):
                event_manager.set_max_queue_size(self.config.get("max_event_queue_size", 1000))
                logger.info(f"[优化] 事件队列大小限制设为 {self.config.get('max_event_queue_size')}")
        except Exception as e:
            logger.debug(f"[优化] 无法设置事件队列大小: {e}")

    def _set_thread_pool_limit(self, max_workers: int):
        """替换 asyncio 默认线程池，限制最大线程数"""
        try:
            loop = asyncio.get_running_loop()
            # 保存原始执行器以便恢复（如果需要）
            if self._original_executor is None:
                self._original_executor = loop._default_executor
            # 创建新的线程池
            new_executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="OptPool")
            loop.set_default_executor(new_executor)
            logger.info(f"[优化] 已将 asyncio 默认线程池大小限制为 {max_workers} 个线程")
        except RuntimeError:
            # 没有运行中的事件循环，暂存配置，等 _on_start 时再设置
            self._pending_cpu_optim = max_workers
            logger.info(f"[优化] 当前无事件循环，将在启动时应用 CPU 优化 (线程池大小={max_workers})")
        except Exception as e:
            logger.error(f"[优化] 设置线程池大小失败: {e}")

    async def _call_other_plugin_optimization(self):
        if not self.config.get("optimize_other_plugins", False):
            return
        if not self.config.get("other_plugin_optimization_enabled", False):
            return

        level = self.config.get("other_plugin_optimization_level", "medium")
        logger.info(f"[优化] 开始调用其他插件的性能优化方法 (级别: {level})")

        try:
            plugin_manager = self.context.get_plugin_manager()
            if plugin_manager is None:
                logger.warning("[优化] 无法获取插件管理器，跳过优化调用")
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
                        logger.debug(f"[优化] 已调用 {plugin.__class__.__name__}.optimize_performance()")
                    except Exception as e:
                        logger.error(f"[优化] 调用 {plugin.__class__.__name__} 优化方法时出错: {e}")
            logger.info(f"[优化] 共调用 {count} 个插件的优化方法")
        except Exception as e:
            logger.error(f"[优化] 扫描插件失败: {e}")

    async def _periodic_optimize(self):
        while True:
            try:
                interval = self.config.get("gc_interval_seconds", 300)
                await asyncio.sleep(interval)

                new_config = self._load_config()
                if new_config != self.config:
                    self.config = new_config
                    self._apply_initial_settings()
                    logger.info("[优化] 配置已热更新")

                if self.config.get("enable_gc_optimization", False):
                    collected = gc.collect()
                    if collected > 0:
                        logger.debug(f"[优化] 主动 GC 回收了 {collected} 个对象")

                days = self.config.get("clear_unused_sessions_days", 0)
                if days > 0:
                    try:
                        session_mgr = self.context.get_session_manager()
                        if session_mgr and hasattr(session_mgr, 'clear_inactive_sessions'):
                            before = datetime.now() - timedelta(days=days)
                            cleared = session_mgr.clear_inactive_sessions(before)
                            if cleared:
                                logger.info(f"[优化] 清除了 {cleared} 个不活跃会话")
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
                logger.error(f"[优化] 后台任务异常: {e}")

    async def _on_start(self):
        # 处理之前未应用的 CPU 优化
        if hasattr(self, '_pending_cpu_optim'):
            self._set_thread_pool_limit(self._pending_cpu_optim)
            delattr(self, '_pending_cpu_optim')

        self._optimize_task = asyncio.create_task(self._periodic_optimize())
        logger.info("[优化] 后台优化任务已启动")

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
            logger.info("[优化] 后台优化任务已停止")
        # 恢复原始线程池（可选）
        if self._original_executor is not None:
            try:
                loop = asyncio.get_running_loop()
                loop.set_default_executor(self._original_executor)
                logger.info("[优化] 已恢复原始线程池")
            except Exception:
                pass

    async def terminate(self):
        await self._on_stop()

    @filter.command("重载优化配置")
    async def reload_config(self, event: AstrMessageEvent):
        old_config = self.config.copy()
        self.config = self._load_config()
        self._apply_initial_settings()
        config_count = len(self.config)
        changed = [k for k in self.config if old_config.get(k) != self.config.get(k)]
        if changed:
            yield event.plain_result(f"✅ 配置已重载（共 {config_count} 项，其中 {len(changed)} 项发生变化）")
        else:
            yield event.plain_result(f"✅ 配置已重载（共 {config_count} 项，无变化）")

    @filter.command("优化其他插件")
    async def call_plugin_optimize(self, event: AstrMessageEvent):
        if not self.config.get("optimize_other_plugins", False):
            yield event.plain_result("⚠️ 总开关「优化其他插件」未开启，无法执行。请在面板中开启。")
            return
        if not self.config.get("other_plugin_optimization_enabled", False):
            yield event.plain_result("⚠️ 子开关「启用调用」未开启，无法执行。请在面板中开启。")
            return

        level = self.config.get("other_plugin_optimization_level", "medium")
        called_plugins = []
        try:
            plugin_manager = self.context.get_plugin_manager()
            if plugin_manager is None:
                yield event.plain_result("❌ 无法获取插件管理器，请检查 AstrBot 版本。")
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
                        called_plugins.append(plugin.__class__.__name__)
                    except Exception as e:
                        logger.error(f"[优化] 调用 {plugin.__class__.__name__} 优化方法时出错: {e}")
            if count == 0:
                yield event.plain_result(f"ℹ️ 未找到任何实现了 optimize_performance 方法的插件（级别：{level}）")
            else:
                if len(called_plugins) <= 5:
                    names = "、".join(called_plugins)
                    yield event.plain_result(f"✅ 已调用 {count} 个插件的优化方法（级别：{level}）：{names}")
                else:
                    yield event.plain_result(f"✅ 已调用 {count} 个插件的优化方法（级别：{level}），包括 {called_plugins[0]} 等")
        except Exception as e:
            logger.error(f"[优化] 扫描插件失败: {e}")
            yield event.plain_result(f"❌ 执行过程中发生错误：{str(e)}")

    @filter.command("手动垃圾回收")
    async def manual_gc(self, event: AstrMessageEvent):
        collected = gc.collect()
        yield event.plain_result(f"🧹 手动垃圾回收完成，共回收 {collected} 个无法访问的对象。")