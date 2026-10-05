import json
import os
from datetime import date
from pathlib import Path

import telebot
from telebot.types import (
	InlineKeyboardButton,
	InlineKeyboardMarkup,
	KeyboardButton,
	ReplyKeyboardMarkup,
)


TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_ID_VALUE = os.getenv("TELEGRAM_ADMIN_ID", "")
if not TOKEN:
	raise RuntimeError("TELEGRAM_BOT_TOKEN environment variable is required")
if not ADMIN_ID_VALUE.isdigit():
	raise RuntimeError("TELEGRAM_ADMIN_ID must be set to your numeric Telegram user ID")

ADMIN_ID = int(ADMIN_ID_VALUE)
DATA_FILE = Path(__file__).with_name("lineups.json")
STATS_FILE = Path(__file__).with_name("stats.json")
bot = telebot.TeleBot(TOKEN)
BOT_USERNAME = ""
ADMIN_PANEL_BUTTON = "🛠 Admin panel"
STATS_BUTTON = "📊 Statistika"

MAPS = {
	"Mirage 🏜": "mirage",
	"Dust 2 🏜": "dust2",
	"Inferno 🏘": "inferno",
	"Ancient 🌿": "ancient",
	"Nuke ☢️": "nuke",
	"Anubis 🐺": "anubis",
}
MAP_NAMES = {key: label for label, key in MAPS.items()}
MAP_ALIASES = {"dust_2": "dust2", "dust-2": "dust2", "d2": "dust2"}
GRENADES = {
	"Smoke ☁️": "smoke",
	"Flash ⚡️": "flash",
	"Molotov 🔥": "molotov",
}
GRENADE_NAMES = {key: label for label, key in GRENADES.items()}
user_maps = {}
pending_uploads = {}
admin_selections = {}


def load_lineups():
	if not DATA_FILE.exists():
		return {}
	with DATA_FILE.open("r", encoding="utf-8") as lineup_file:
		data = json.load(lineup_file)
	if not isinstance(data, dict):
		raise ValueError("lineups.json must contain a JSON object")
	return data


lineups = load_lineups()


def save_lineups():
	temporary_file = DATA_FILE.with_suffix(".tmp")
	temporary_file.write_text(
		json.dumps(lineups, ensure_ascii=False, indent=2), encoding="utf-8"
	)
	temporary_file.replace(DATA_FILE)


def load_statistics():
	if not STATS_FILE.exists():
		return {
			"users": set(),
			"date": date.today().isoformat(),
			"today_users": set(),
		}
	with STATS_FILE.open("r", encoding="utf-8") as stats_file:
		data = json.load(stats_file)
	if not isinstance(data, dict) or not isinstance(data.get("users"), list):
		raise ValueError("stats.json must contain a users list")
	return {
		"users": {str(user_id) for user_id in data["users"]},
		"date": data.get("date", date.today().isoformat()),
		"today_users": {str(user_id) for user_id in data.get("today_users", [])},
	}


statistics = load_statistics()


def save_statistics():
	data = {
		"users": sorted(statistics["users"]),
		"date": statistics["date"],
		"today_users": sorted(statistics["today_users"]),
	}
	temporary_file = STATS_FILE.with_suffix(".tmp")
	temporary_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
	temporary_file.replace(STATS_FILE)


def record_user_activity(user_id):
	if user_id == ADMIN_ID:
		return

	today = date.today().isoformat()
	if statistics["date"] != today:
		statistics["date"] = today
		statistics["today_users"] = set()

	user_id = str(user_id)
	changed = user_id not in statistics["users"] or user_id not in statistics["today_users"]
	statistics["users"].add(user_id)
	statistics["today_users"].add(user_id)
	if changed:
		save_statistics()


def statistics_message():
	today_users = statistics["today_users"] if statistics["date"] == date.today().isoformat() else set()
	return (
		"📊 Bot statistikasi\n"
		f"Jami foydalanganlar: {len(statistics['users'])}\n"
		f"Bugun faol bo‘lganlar: {len(today_users)}"
	)


def main_menu(user_id=None):
	markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
	markup.add(*(KeyboardButton(name) for name in MAPS))
	if user_id == ADMIN_ID:
		markup.add(KeyboardButton(ADMIN_PANEL_BUTTON), KeyboardButton(STATS_BUTTON))
	return markup


def nade_menu():
	markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=3)
	markup.add(
		KeyboardButton("Smoke ☁️"),
		KeyboardButton("Flash ⚡️"),
		KeyboardButton("Molotov 🔥"),
	)
	markup.add(KeyboardButton("🔙 Ortga"))
	return markup


def admin_map_menu():
	markup = InlineKeyboardMarkup(row_width=2)
	markup.add(
		*(InlineKeyboardButton(MAP_NAMES[key], callback_data=f"admin_map:{key}") for key in MAP_NAMES)
	)
	return markup


def admin_grenade_menu():
	markup = InlineKeyboardMarkup(row_width=3)
	markup.add(
		*(InlineKeyboardButton(name, callback_data=f"admin_grenade:{key}") for key, name in GRENADE_NAMES.items())
	)
	return markup


def format_video_caption(video, map_key, grenade_key):
	description = (video.get("caption") or "").strip()
	if not description:
		description = f"{MAP_NAMES[map_key]} / {GRENADE_NAMES[grenade_key]}"

	footer = f"@{BOT_USERNAME}" if BOT_USERNAME else ""
	if not footer:
		return description[:1024]

	description = description[: 1024 - len(footer) - 2].rstrip()
	return f"{description}\n\n{footer}" if description else footer


@bot.message_handler(commands=["start"])
def send_welcome(message):
	if message.from_user:
		record_user_activity(message.from_user.id)
		user_maps.pop((message.chat.id, message.from_user.id), None)
	bot.send_message(
		message.chat.id,
		"CS2 Raskidkalar botiga xush kelibsiz! Kerakli xaritani tanlang:",
		reply_markup=main_menu(message.from_user.id if message.from_user else None),
	)


@bot.message_handler(commands=["admin"])
def open_admin_panel(message):
	if not message.from_user or message.from_user.id != ADMIN_ID:
		bot.reply_to(message, "Bu buyruq faqat bot administratori uchun.")
		return
	bot.send_message(
		message.chat.id,
		"Video joylash uchun xaritani tanlang:",
		reply_markup=admin_map_menu(),
	)


@bot.callback_query_handler(
	func=lambda call: (call.data or "").startswith(("admin_map:", "admin_grenade:"))
)
def handle_admin_selection(call):
	if not call.from_user or call.from_user.id != ADMIN_ID:
		bot.answer_callback_query(call.id, "Bu panel faqat administrator uchun.", show_alert=True)
		return

	user_id = call.from_user.id
	if call.data.startswith("admin_map:"):
		map_key = call.data.split(":", 1)[1]
		if map_key not in MAP_NAMES:
			bot.answer_callback_query(call.id, "Xarita topilmadi.", show_alert=True)
			return
		admin_selections[user_id] = map_key
		bot.answer_callback_query(call.id)
		bot.edit_message_text(
			f"{MAP_NAMES[map_key]} tanlandi. Granatani tanlang:",
			call.message.chat.id,
			call.message.message_id,
			reply_markup=admin_grenade_menu(),
		)
		return

	grenade_key = call.data.split(":", 1)[1]
	map_key = admin_selections.get(user_id)
	if grenade_key not in GRENADE_NAMES or not map_key:
		bot.answer_callback_query(call.id, "Avval xaritani tanlang.", show_alert=True)
		return

	pending_uploads[user_id] = (map_key, grenade_key)
	admin_selections.pop(user_id, None)
	bot.answer_callback_query(call.id)
	bot.edit_message_text(
		f"{MAP_NAMES[map_key]} / {GRENADE_NAMES[grenade_key]} videosini caption bilan yuboring.\n"
		"Captionga granatani qayerga tashlash kerakligini yozing.",
		call.message.chat.id,
		call.message.message_id,
	)


@bot.message_handler(commands=["addvideo"])
def start_video_upload(message):
	if not message.from_user or message.from_user.id != ADMIN_ID:
		bot.reply_to(message, "Bu buyruq faqat bot administratori uchun.")
		return

	parts = (message.text or "").split()
	if len(parts) == 1:
		open_admin_panel(message)
		return
	if len(parts) != 3:
		bot.reply_to(
			message,
			"Ishlatish: /addvideo <map> <grenade>\n"
			"Misol: /addvideo mirage smoke\n"
			f"Xaritalar: {', '.join(MAPS.values())}\n"
			"Granatalar: smoke, flash, molotov",
		)
		return

	map_key = MAP_ALIASES.get(parts[1].lower(), parts[1].lower())
	grenade_key = parts[2].lower()
	if map_key not in MAP_NAMES or grenade_key not in GRENADE_NAMES:
		bot.reply_to(message, "Xarita yoki granata nomi noto'g'ri. /addvideo yordamidan foydalaning.")
		return

	pending_uploads[message.from_user.id] = (map_key, grenade_key)
	bot.reply_to(
		message,
		f"{MAP_NAMES[map_key]} / {GRENADE_NAMES[grenade_key]} videosini yuboring. "
		"Video izohini lineup nomi sifatida qo'shishingiz mumkin.",
	)


@bot.message_handler(content_types=["video"])
def receive_video(message):
	if not message.from_user:
		return
	upload = pending_uploads.get(message.from_user.id)
	if message.from_user.id != ADMIN_ID or not upload:
		return

	map_key, grenade_key = upload
	map_lineups = lineups.setdefault(map_key, {})
	videos = map_lineups.setdefault(grenade_key, [])
	videos.append(
		{
			"file_id": message.video.file_id,
			"caption": message.caption or "",
		}
	)
	save_lineups()
	pending_uploads.pop(message.from_user.id, None)
	bot.reply_to(
		message,
		f"Video saqlandi: {MAP_NAMES[map_key]} / {GRENADE_NAMES[grenade_key]}.",
	)


@bot.message_handler(content_types=["text"])
def handle_text(message):
	text = (message.text or "").strip()
	if not message.from_user:
		return
	record_user_activity(message.from_user.id)
	if text.startswith("/"):
		return

	selection_key = (message.chat.id, message.from_user.id)
	if text == STATS_BUTTON:
		if message.from_user.id == ADMIN_ID:
			bot.send_message(message.chat.id, statistics_message())
		else:
			bot.reply_to(message, "Bu bo‘lim faqat bot administratori uchun.")
		return

	if text == ADMIN_PANEL_BUTTON:
		user_maps.pop(selection_key, None)
		open_admin_panel(message)
		return

	if text == "🔙 Ortga":
		user_maps.pop(selection_key, None)
		bot.send_message(
			message.chat.id,
			"Asosiy menyuga qaytdik. Xaritani tanlang:",
			reply_markup=main_menu(message.from_user.id),
		)
		return

	if text in MAPS:
		user_maps[selection_key] = MAPS[text]
		bot.send_message(
			message.chat.id,
			f"{text} xaritasi tanlandi. Qaysi granata kerak?",
			reply_markup=nade_menu(),
		)
		return

	if text in GRENADES:
		map_key = user_maps.get(selection_key)
		if not map_key:
			bot.send_message(
				message.chat.id,
				"Avval xaritani tanlang:",
				reply_markup=main_menu(message.from_user.id),
			)
			return

		grenade_key = GRENADES[text]
		videos = lineups.get(map_key, {}).get(grenade_key, [])
		if not videos:
			bot.send_message(
				message.chat.id,
				f"{MAP_NAMES[map_key]} uchun {text} videosi hozircha yo'q.",
				reply_markup=nade_menu(),
			)
			return

		for video in videos:
			caption = format_video_caption(video, map_key, grenade_key)
			bot.send_video(message.chat.id, video["file_id"], caption=caption)
		return

	bot.send_message(
		message.chat.id,
		"Menyudagi xarita yoki granata tugmalaridan birini tanlang.",
		reply_markup=main_menu(message.from_user.id) if selection_key not in user_maps else nade_menu(),
	)


if __name__ == "__main__":
	bot_info = bot.get_me()
	BOT_USERNAME = bot_info.username or ""
	print(f"Bot ishga tushdi: @{BOT_USERNAME}" if BOT_USERNAME else "Bot ishga tushdi...")
	bot.infinity_polling(skip_pending=True)
