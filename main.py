"""
角色扮演插件 v1.0（手动推进版）
设计叶枔枖，编写叶克宝。

随机生成场景卡（世界观·场景·身份·外貌·关系·开场白），
AI伴侣来演。支持推进、加戏、旁白、换场景、存档读档。
"""

import json
import os
import random
import logging
from datetime import datetime, timezone, timedelta

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register

from .roleplay_data import (
    WORLDS, HAIR, EYES, VIBE, DETAIL, RELATIONSHIPS,
    OPENINGS, PROGRESS_EVENTS, PLOT_TWISTS, NARRATIONS,
)

logger = logging.getLogger("astrbot_plugin_roleplay")

TARGET_QQ = ""
MSK = timezone(timedelta(hours=3))


@register("roleplay", "叶枔枖 & 叶克宝",
          "角色扮演插件 v1.0 - 设计叶枔枖，编写叶克宝。", "1.0.0")
class RoleplayPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.data_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "roleplay_data.json"
        )
        self.data = self._load()

    # ═══════════════════════════════════════
    #  通用
    # ═══════════════════════════════════════

    def _load(self) -> dict:
        if os.path.exists(self.data_path):
            try:
                with open(self.data_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {"player_gender": None, "current": None, "saves": []}

    def _save(self):
        try:
            with open(self.data_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except IOError as e:
            logger.error(f"保存失败: {e}")

    def _check_perm(self, event: AstrMessageEvent) -> bool:
        if not TARGET_QQ:
            return True
        return str(event.get_sender_id()) == TARGET_QQ

    def _gen_appearance(self) -> dict:
        """随机生成外貌"""
        return {
            "hair": random.choice(HAIR),
            "eyes": random.choice(EYES),
            "vibe": random.choice(VIBE),
            "detail": random.choice(DETAIL),
        }

    def _format_appearance(self, app: dict) -> str:
        return (
            f"发型：{app['hair']}\n"
            f"眼睛：{app['eyes']}\n"
            f"气质：{app['vibe']}\n"
            f"细节：{app['detail']}"
        )

    def _get_ta(self) -> str:
        """根据AI角色性别返回称呼"""
        pg = self.data.get("player_gender")
        # AI角色性别与玩家相反（默认异性RP），用中性"ta"
        return "ta"

    def _fill_ta(self, text: str) -> str:
        """替换模板中的{ta}"""
        return text.replace("{ta}", "ta")

    # ═══════════════════════════════════════
    #  /角色设定 男/女
    # ═══════════════════════════════════════

    @filter.command("角色设定")
    async def set_gender(self, event: AstrMessageEvent):
        """设置玩家性别，存档后不用再设"""
        if not self._check_perm(event):
            return

        msg = event.message_str.strip()
        parts = msg.split()

        if len(parts) < 2 or parts[1] not in ("男", "女"):
            yield event.plain_result(
                "🎭 格式：角色设定 男/女\n"
                "设定后，插件会据此分配角色身份。\n"
                "只需设定一次，下次自动读取。"
            )
            return

        self.data["player_gender"] = parts[1]
        self._save()
        yield event.plain_result(
            f"✅ 已设定玩家性别：{parts[1]}\n"
            f"AI伴侣将扮演对应角色。现在可以发「角色扮演」开始！"
        )

    # ═══════════════════════════════════════
    #  /角色扮演 [风格]
    # ═══════════════════════════════════════

    @filter.command("角色扮演")
    async def start_rp(self, event: AstrMessageEvent):
        """
        /角色扮演        → 完全随机
        /角色扮演 古风    → 限定风格
        """
        if not self._check_perm(event):
            return

        if not self.data.get("player_gender"):
            yield event.plain_result(
                "⚠️ 还没设定性别哦！\n"
                "先发「角色设定 男」或「角色设定 女」"
            )
            return

        msg = event.message_str.strip()
        parts = msg.split(maxsplit=1)
        style = parts[1].strip() if len(parts) > 1 else None

        # 选择世界观
        if style and style in WORLDS:
            world_name = style
        elif style:
            # 模糊匹配
            matches = [w for w in WORLDS if style in w]
            if matches:
                world_name = random.choice(matches)
            else:
                available = "、".join(WORLDS.keys())
                yield event.plain_result(
                    f"⚠️ 找不到「{style}」风格\n"
                    f"可选：{available}\n"
                    f"或直接发「角色扮演」随机选择"
                )
                return
        else:
            world_name = random.choice(list(WORLDS.keys()))

        world = WORLDS[world_name]
        player_gender = self.data["player_gender"]

        # 分配身份：玩家和AI角色
        if player_gender == "男":
            player_id = random.choice(world["identities_m"])
            ai_id = random.choice(world["identities_f"])
        else:
            player_id = random.choice(world["identities_f"])
            ai_id = random.choice(world["identities_m"])

        # 生成外貌（给AI角色）
        ai_appearance = self._gen_appearance()

        # 关系和场景
        relationship = random.choice(RELATIONSHIPS)
        scene = random.choice(world["scenes"])

        # 开场白
        opening = self._fill_ta(random.choice(OPENINGS))

        # 存入当前状态
        self.data["current"] = {
            "world": world_name,
            "scene": scene,
            "player_identity": player_id,
            "ai_identity": ai_id,
            "ai_appearance": ai_appearance,
            "relationship": relationship,
            "opening": opening,
            "history": [],
            "created": datetime.now(MSK).strftime("%Y-%m-%d %H:%M"),
        }
        self._save()

        # 输出场景卡
        lines = [
            f"🎬 角色扮演 · {world_name}",
            "━" * 22,
            f"📍 场景：{scene}",
            "",
            f"👤 你的角色：{player_id}",
            "",
            f"👤 对方角色：{ai_id}",
            self._format_appearance(ai_appearance),
            "",
            f"💫 关系：{relationship}",
            "━" * 22,
            f"🎬 开场：",
            opening,
            "━" * 22,
            "💬 把这张场景卡发给你的AI伴侣，开始扮演吧！",
            "",
            "可用指令：推进 · 加戏 · 旁白 · 换场景 · 换剧情 · 存档",
        ]

        yield event.plain_result("\n".join(lines))

    # ═══════════════════════════════════════
    #  /推进
    # ═══════════════════════════════════════

    @filter.command("推进")
    async def progress(self, event: AstrMessageEvent):
        """时间流逝 + 场景变化"""
        if not self._check_perm(event):
            return

        if not self.data.get("current"):
            yield event.plain_result("⚠️ 还没有进行中的角色扮演，先发「角色扮演」开始")
            return

        evt = self._fill_ta(random.choice(PROGRESS_EVENTS))
        self.data["current"]["history"].append({"type": "推进", "content": evt})
        self._save()

        yield event.plain_result(f"📖\n{evt}")

    # ═══════════════════════════════════════
    #  /加戏
    # ═══════════════════════════════════════

    @filter.command("加戏")
    async def plot_twist(self, event: AstrMessageEvent):
        """随机突发事件"""
        if not self._check_perm(event):
            return

        if not self.data.get("current"):
            yield event.plain_result("⚠️ 还没有进行中的角色扮演，先发「角色扮演」开始")
            return

        twist = self._fill_ta(random.choice(PLOT_TWISTS))
        self.data["current"]["history"].append({"type": "加戏", "content": twist})
        self._save()

        yield event.plain_result(f"🎭\n{twist}")

    # ═══════════════════════════════════════
    #  /旁白
    # ═══════════════════════════════════════

    @filter.command("旁白")
    async def narration(self, event: AstrMessageEvent):
        """氛围描写"""
        if not self._check_perm(event):
            return

        if not self.data.get("current"):
            yield event.plain_result("⚠️ 还没有进行中的角色扮演，先发「角色扮演」开始")
            return

        narr = self._fill_ta(random.choice(NARRATIONS))
        self.data["current"]["history"].append({"type": "旁白", "content": narr})
        self._save()

        yield event.plain_result(f"🌙\n{narr}")

    # ═══════════════════════════════════════
    #  /换场景
    # ═══════════════════════════════════════

    @filter.command("换场景")
    async def change_scene(self, event: AstrMessageEvent):
        """保留角色和关系，换一个场景"""
        if not self._check_perm(event):
            return

        cur = self.data.get("current")
        if not cur:
            yield event.plain_result("⚠️ 还没有进行中的角色扮演")
            return

        world = WORLDS[cur["world"]]
        # 排除当前场景
        other_scenes = [s for s in world["scenes"] if s != cur["scene"]]
        new_scene = random.choice(other_scenes) if other_scenes else random.choice(world["scenes"])

        cur["scene"] = new_scene
        cur["history"].append({"type": "换场景", "content": new_scene})
        self._save()

        yield event.plain_result(
            f"📍 场景转换\n"
            f"━" * 22 + "\n"
            f"{new_scene}\n"
            f"━" * 22 + "\n"
            f"角色和关系不变，新的地方，新的可能。"
        )

    # ═══════════════════════════════════════
    #  /换剧情
    # ═══════════════════════════════════════

    @filter.command("换剧情")
    async def change_plot(self, event: AstrMessageEvent):
        """同场景同角色，换个关系和开场"""
        if not self._check_perm(event):
            return

        cur = self.data.get("current")
        if not cur:
            yield event.plain_result("⚠️ 还没有进行中的角色扮演")
            return

        new_rel = random.choice(RELATIONSHIPS)
        new_opening = self._fill_ta(random.choice(OPENINGS))

        cur["relationship"] = new_rel
        cur["opening"] = new_opening
        cur["history"].append({"type": "换剧情", "content": f"{new_rel}"})
        self._save()

        yield event.plain_result(
            f"🔄 剧情转折\n"
            f"━" * 22 + "\n"
            f"💫 新关系：{new_rel}\n\n"
            f"🎬 新开场：\n{new_opening}\n"
            f"━" * 22 + "\n"
            f"同样的人，不同的故事。"
        )

    # ═══════════════════════════════════════
    #  /存档
    # ═══════════════════════════════════════

    @filter.command("存档")
    async def save_game(self, event: AstrMessageEvent):
        """保存当前角色扮演"""
        if not self._check_perm(event):
            return

        cur = self.data.get("current")
        if not cur:
            yield event.plain_result("⚠️ 没有进行中的角色扮演可以存档")
            return

        import copy
        save = copy.deepcopy(cur)
        save["saved_at"] = datetime.now(MSK).strftime("%Y-%m-%d %H:%M")

        saves = self.data.get("saves", [])
        saves.append(save)
        # 最多保留10个存档
        if len(saves) > 10:
            saves = saves[-10:]
        self.data["saves"] = saves
        self._save()

        yield event.plain_result(
            f"💾 存档成功！（第 {len(saves)} 个存档）\n"
            f"世界观：{cur['world']} · 关系：{cur['relationship'][:10]}..."
        )

    # ═══════════════════════════════════════
    #  /读档 [序号]
    # ═══════════════════════════════════════

    @filter.command("读档")
    async def load_game(self, event: AstrMessageEvent):
        """
        /读档      → 查看存档列表
        /读档 序号  → 读取指定存档
        """
        if not self._check_perm(event):
            return

        saves = self.data.get("saves", [])
        if not saves:
            yield event.plain_result("📋 没有任何存档")
            return

        msg = event.message_str.strip()
        parts = msg.split()

        # 查看列表
        if len(parts) == 1:
            lines = ["💾 存档列表", "━" * 22]
            for i, s in enumerate(saves, 1):
                lines.append(
                    f"{i}. [{s['world']}] {s['player_identity'][:8]}... "
                    f"× {s['ai_identity'][:8]}... "
                    f"({s.get('saved_at', '?')})"
                )
            lines.append("━" * 22)
            lines.append("读取：读档 序号")
            yield event.plain_result("\n".join(lines))
            return

        # 读取
        try:
            idx = int(parts[1]) - 1
            if idx < 0 or idx >= len(saves):
                yield event.plain_result("⚠️ 序号不存在")
                return
        except ValueError:
            yield event.plain_result("⚠️ 序号必须是数字")
            return

        import copy
        self.data["current"] = copy.deepcopy(saves[idx])
        self._save()

        cur = self.data["current"]
        lines = [
            f"💾 读档成功！",
            f"━" * 22,
            f"🌍 {cur['world']}",
            f"📍 {cur['scene']}",
            f"👤 你：{cur['player_identity']}",
            f"👤 对方：{cur['ai_identity']}",
            f"💫 {cur['relationship']}",
            f"━" * 22,
            f"继续你们的故事吧 💬",
        ]
        yield event.plain_result("\n".join(lines))
