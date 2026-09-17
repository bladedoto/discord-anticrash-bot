import asyncio
from datetime import datetime, timedelta, timezone
import discord
from discord.ext import commands

TOKEN = "YOUR TOKEN"

# Настройки защиты от банов
BAN_LIMIT = 3  # Максимум банов
BAN_TIME_WINDOW = 2  # Временное окно (в минутах)

intents = discord.Intents.default()
intents.members = True
intents.moderation = True

bot = commands.Bot(command_prefix="!", intents=intents)

# История банов: {mod_id: [datetime1, datetime2, ...]}
ban_history = {}


@bot.event
async def on_ready():
  print(f"Антикраш бот запущен как {bot.user}")


# --- 1. ЗАЩИТА ОТ ОПАСНЫХ БОТОВ (Админ-права) ---
@bot.event
async def on_member_join(member: discord.Member):
  if not member.bot:
    return

  # Проверяем, есть ли у зашедшего бота права администратора
  if member.guild_permissions.administrator:
    await asyncio.sleep(1)  # Небольшая пауза для записи в аудит-лог

    inviter = None
    async for entry in member.guild.audit_logs(
        limit=5, action=discord.AuditLogAction.bot_add
    ):
      if entry.target.id == member.id:
        inviter = entry.user
        break

    try:
      # Баним вредоносного бота
      await member.ban(reason="Антикраш: Бот с правами администратора")

      # Кикаем человека, который его пригласил
      if inviter and inviter.id != member.guild.owner_id:
        await member.guild.kick(
            inviter, reason="Антикраш: Пригласил бота с правами администратора"
        )

      print(
          f"Заблокирован бот-админ {member} и кикнут пригласивший: {inviter}"
      )
    except discord.Forbidden:
      print("Ошибка: У бота недостаточно прав для бана/кика.")


# --- 2. ЗАЩИТА ОТ МАССОВЫХ БАНОВ ---
@bot.event
async def on_ban_add(guild: discord.Guild, user: discord.User):
  await asyncio.sleep(1)

  async for entry in guild.audit_logs(
      limit=5, action=discord.AuditLogAction.ban
  ):
    if entry.target.id == user.id:
      executor = entry.user

      # Игнорируем самого антикраш-бота и владельца сервера
      if executor.bot or executor.id == guild.owner_id:
        return

      now = datetime.now(timezone.utc)
      mod_id = executor.id

      if mod_id not in ban_history:
        ban_history[mod_id] = []

      # Очищаем записи старше 2 минут
      cutoff_time = now - timedelta(minutes=BAN_TIME_WINDOW)
      ban_history[mod_id] = [t for t in ban_history[mod_id] if t > cutoff_time]

      # Фиксируем бан
      ban_history[mod_id].append(now)

      # Проверяем лимит
      if len(ban_history[mod_id]) >= BAN_LIMIT:
        mod_member = guild.get_member(executor.id)
        if mod_member:
          try:
            # Кикаем модератора за превышение лимита
            await mod_member.kick(
                reason="Антикраш: Превышен лимит банов (более 3 за 2 минуты)"
            )
            print(
                f"Модератор {executor} кикнут за превышение лимита банов."
            )
            ban_history[mod_id] = []
          except discord.Forbidden:
            print(f"Ошибка: Не удалось кикнуть модератора {executor}.")
      break


bot.run(TOKEN)