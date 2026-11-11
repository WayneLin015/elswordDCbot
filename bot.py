import os
import json
from dataclasses import dataclass, field

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv


MAX_PLAYERS = 6


def load_job_families() -> list[dict[str, object]]:
    with open("config.json", "r", encoding="utf-8") as config_file:
        config = json.load(config_file)
    families = config.get("job_families", [])
    if len(families) != 15 or any(
        not isinstance(family, dict)
        or not isinstance(family.get("name"), str)
        or len(family.get("jobs", [])) != 4
        for family in families
    ):
        raise RuntimeError("config.json 必須包含 15 個職業系，且每系 4 個職業。")
    return [
        {"name": str(family["name"]), "jobs": [str(job) for job in family["jobs"]]}
        for family in families
    ]


JOB_FAMILIES = load_job_families()


@dataclass
class Raid:
    raid_id: int
    name: str
    time_text: str
    leader_id: int
    channel_id: int
    message_id: int | None = None
    members: list[int] = field(default_factory=list)
    roles: dict[int, str] = field(default_factory=dict)
    closed: bool = False


active_raids: dict[int, Raid] = {}
next_raid_id = 1


def member_mentions(raid: Raid) -> str:
    if not raid.members:
        return "尚無隊員"
    return "\n".join(
        f"{index}. <@{user_id}> — {raid.roles.get(user_id, '未選擇職業')}"
        for index, user_id in enumerate(raid.members, start=1)
    )


def raid_embed(raid: Raid) -> discord.Embed:
    if raid.closed:
        status = "已關閉"
    elif len(raid.members) >= MAX_PLAYERS:
        status = "已滿員"
    else:
        status = "招募中"

    embed = discord.Embed(
        title=f"【{raid.name}】",
        description=(
            f"時間：{raid.time_text}\n"
            f"目前：{len(raid.members)} / {MAX_PLAYERS}\n"
            f"狀態：{status}"
        ),
        colour=discord.Colour.blurple(),
    )
    embed.add_field(name="隊長", value=f"<@{raid.leader_id}>", inline=False)
    embed.add_field(name="目前成員", value=member_mentions(raid), inline=False)
    return embed


class JobSelect(discord.ui.Select):
    def __init__(self, raid: Raid, user_id: int, parent_view: "RaidView", jobs: list[str]):
        self.raid = raid
        self.user_id = user_id
        self.parent_view = parent_view
        options = [discord.SelectOption(label=job, value=job) for job in jobs]
        super().__init__(placeholder="選擇你加入的職業", options=options)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("這不是你的職業選單。", ephemeral=True)
            return
        if self.raid.closed:
            await interaction.response.edit_message(content="這個招募已關閉。", view=None)
            return
        if self.user_id not in self.raid.members:
            if len(self.raid.members) >= MAX_PLAYERS:
                await interaction.response.edit_message(content="隊伍已經滿 6 人。", view=None)
                return
            self.raid.members.append(self.user_id)
        self.raid.roles[self.user_id] = self.values[0]
        await interaction.response.edit_message(
            content=f"已加入【{self.raid.name}】，職業：{self.values[0]}",
            view=None,
        )
        await self.parent_view.refresh_message(interaction)
        if len(self.raid.members) == MAX_PLAYERS:
            await interaction.followup.send(
                f"{interaction.user.mention} 加入後，副本隊伍已滿 6 人！",
                allowed_mentions=discord.AllowedMentions(users=True),
            )


class FamilySelect(discord.ui.Select):
    def __init__(self, raid: Raid, user_id: int, parent_view: "RaidView"):
        self.raid = raid
        self.user_id = user_id
        self.parent_view = parent_view
        options = [
            discord.SelectOption(label=family["name"], value=str(index))
            for index, family in enumerate(JOB_FAMILIES)
        ]
        super().__init__(placeholder="先選擇職業系", options=options)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("這不是你的職業選單。", ephemeral=True)
            return
        family_index = int(self.values[0])
        await interaction.response.edit_message(
            content="請選擇你加入的職業：",
            view=RoleSelectView(self.raid, self.user_id, self.parent_view, family_index),
        )


class RoleSelectView(discord.ui.View):
    def __init__(self, raid: Raid, user_id: int, parent_view: "RaidView", family_index: int | None = None):
        super().__init__(timeout=60)
        if family_index is None:
            self.add_item(FamilySelect(raid, user_id, parent_view))
        else:
            self.add_item(JobSelect(raid, user_id, parent_view, JOB_FAMILIES[family_index]["jobs"]))


class RaidView(discord.ui.View):
    def __init__(self, raid: Raid):
        super().__init__(timeout=None)
        self.raid = raid
        self.message: discord.Message | None = None

    async def refresh(self, interaction: discord.Interaction) -> None:
        await interaction.message.edit(embed=raid_embed(self.raid), view=self)

    async def refresh_message(self, interaction: discord.Interaction) -> None:
        if self.message is None:
            return
        await self.message.edit(embed=raid_embed(self.raid), view=self)

    @discord.ui.button(label="加入隊伍", style=discord.ButtonStyle.success)
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.raid.closed:
            await interaction.response.send_message("這個招募已關閉。", ephemeral=True)
            return
        if len(self.raid.members) >= MAX_PLAYERS:
            await interaction.response.send_message("隊伍已經滿 6 人。", ephemeral=True)
            return
        if interaction.user.id in self.raid.members:
            await interaction.response.send_message(
                f"你已經加入，現在職業是：{self.raid.roles.get(interaction.user.id, '未選擇職業')}。",
                ephemeral=True,
            )
            return
        await interaction.response.send_message(
            "請選擇你這次加入的職業（不會限制職業數量）：",
            view=RoleSelectView(self.raid, interaction.user.id, self),
            ephemeral=True,
        )

    @discord.ui.button(label="退出隊伍", style=discord.ButtonStyle.danger)
    async def leave(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in self.raid.members:
            await interaction.response.send_message("你目前不在隊伍裡。", ephemeral=True)
            return
        self.raid.members.remove(interaction.user.id)
        self.raid.roles.pop(interaction.user.id, None)
        await interaction.response.edit_message(embed=raid_embed(self.raid), view=self)

    @discord.ui.button(label="查看名單", style=discord.ButtonStyle.secondary)
    async def roster(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            f"【{self.raid.name}】目前名單：\n{member_mentions(self.raid)}",
            ephemeral=True,
        )

    @discord.ui.button(label="關閉招募", style=discord.ButtonStyle.secondary)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.raid.leader_id:
            await interaction.response.send_message("只有隊長可以關閉招募。", ephemeral=True)
            return
        self.raid.closed = True
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(embed=raid_embed(self.raid), view=self)


class RaidBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.tree.sync()

    async def on_ready(self):
        print(f"已登入：{self.user}（ID: {self.user.id}）")


bot = RaidBot()


@bot.tree.command(name="raid_create", description="建立一個 6 人副本招募")
@app_commands.describe(name="副本名稱", time="副本時間，例如今晚 21:00")
async def raid_create(interaction: discord.Interaction, name: str, time: str):
    global next_raid_id
    if any(
        raid.channel_id == interaction.channel_id
        and raid.name.casefold() == name.casefold()
        and not raid.closed
        for raid in active_raids.values()
    ):
        await interaction.response.send_message(
            "這個頻道已經有同名的進行中招募，請使用不同名稱。", ephemeral=True
        )
        return

    raid = Raid(
        raid_id=next_raid_id,
        name=name,
        time_text=time,
        leader_id=interaction.user.id,
        channel_id=interaction.channel_id,
    )
    next_raid_id += 1
    active_raids[raid.raid_id] = raid
    view = RaidView(raid)
    await interaction.response.send_message(embed=raid_embed(raid), view=view)
    message = await interaction.original_response()
    raid.message_id = message.id
    view.message = message


@bot.tree.command(name="raid_invite", description="標記成員來參加目前的副本招募")
@app_commands.describe(member="要通知的伺服器成員", raid_name="要邀請的招募名稱")
async def raid_invite(
    interaction: discord.Interaction, member: discord.Member, raid_name: str
):
    matching_raids = [
        raid
        for raid in active_raids.values()
        if raid.channel_id == interaction.channel_id
        and raid.name.casefold() == raid_name.casefold()
        and not raid.closed
    ]
    raid = matching_raids[0] if len(matching_raids) == 1 else None
    if raid is None or raid.closed:
        await interaction.response.send_message(
            "找不到這個頻道中同名的進行中招募，或同名招募不只一個。",
            ephemeral=True,
        )
        return
    if interaction.user.id != raid.leader_id:
        await interaction.response.send_message("只有隊長可以標記成員。", ephemeral=True)
        return
    await interaction.response.send_message(
        f"{member.mention} 隊長邀請你參加【{raid.name}】，請在招募訊息按「加入隊伍」。",
        allowed_mentions=discord.AllowedMentions(users=True),
    )


token = os.getenv("DISCORD_TOKEN")
if not token:
    load_dotenv()
    token = os.getenv("DISCORD_TOKEN")

if not token:
    raise RuntimeError("找不到 DISCORD_TOKEN，請設定 .env 或環境變數。")

bot.run(token)

