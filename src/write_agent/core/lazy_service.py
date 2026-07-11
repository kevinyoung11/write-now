"""
延迟服务代理 - 推迟服务单例的创建时机

一些服务（RAG/向量库、爬虫、工作流编排等）初始化开销较大。以前每个路由模块
都会在导入时立刻创建自己的服务单例（`service = get_xxx_service()`），这意味着
只要应用启动/冷启动一次，就要把所有功能的重依赖都初始化一遍——哪怕这次请求
只是要读取一篇笔记，也要等 RAG 向量库、爬虫客户端等全部初始化完毕。

LazyService 包一层薄代理：直到第一次真正访问其属性/方法时，才调用 getter
创建真正的服务实例。这样每个路由模块仍然可以用原来的写法
（`service.some_method(...)`），也不影响测试里
`monkeypatch.setattr(service, "some_method", fake)` 这种打桩方式——setattr 会
触发实例的创建，把桩打在真正被路由代码使用的那个对象上。
"""
from __future__ import annotations

from typing import Callable, Generic, TypeVar

T = TypeVar("T")


class LazyService(Generic[T]):
    def __init__(self, getter: Callable[[], T]):
        object.__setattr__(self, "_getter", getter)
        object.__setattr__(self, "_instance", None)

    def _resolve(self) -> T:
        instance = self.__dict__["_instance"]
        if instance is None:
            instance = self.__dict__["_getter"]()
            object.__setattr__(self, "_instance", instance)
        return instance

    def __getattr__(self, name: str):
        return getattr(self._resolve(), name)

    def __setattr__(self, name: str, value) -> None:
        setattr(self._resolve(), name, value)
