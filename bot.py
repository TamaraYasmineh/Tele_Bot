from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, CallbackQueryHandler, filters
)
from telegram import Bot
import pandas as pd
import os
import random

DATA_FILE = 'bills.xlsx'
SUBSCRIBERS_FILE = 'subscribers.txt'
ADMIN_ID = 6594756464  

def get_main_menu(user_id=None) -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("أرسل لي المعرف الشخصي الخاص بك", callback_data='send_id')],
        [InlineKeyboardButton("مساعدة", callback_data='help')],
    ]
    if user_id == ADMIN_ID:
        keyboard.append([InlineKeyboardButton("رفع ملف Excel", callback_data='upload_file')])
        keyboard.append([InlineKeyboardButton("إرسال بث", callback_data='broadcast')])
        keyboard.append([InlineKeyboardButton("🧹 تنظيف الواجهة", callback_data='reset_ui')])
    return InlineKeyboardMarkup(keyboard)

def load_subscribers():
    if not os.path.exists(SUBSCRIBERS_FILE):
        return set()
    with open(SUBSCRIBERS_FILE, 'r', encoding='utf-8') as f:
        return set(line.strip() for line in f if line.strip().isdigit())

def save_subscriber(user_id: int):
    subscribers = load_subscribers()
    if str(user_id) not in subscribers:
        with open(SUBSCRIBERS_FILE, 'a', encoding='utf-8') as f:
            f.write(f"{user_id}\n")

def generate_unique_ids(df):
    used_ids = set(df['ID'].dropna().astype(str).tolist())
    new_ids = []

    for _, row in df.iterrows():
        if pd.isna(row['ID']):
            new_id = ''.join(random.choices('0123456789', k=8))
            while new_id in used_ids:
                new_id = ''.join(random.choices('0123456789', k=8))
            used_ids.add(new_id)
            new_ids.append(new_id)
        else:
            new_ids.append(str(int(row['ID'])))
    df['ID'] = new_ids
    return df

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    save_subscriber(user_id)
    await update.message.reply_text(
        "  أهلاً بك عزيزي المشترك\n"
        " أرسل رقم المعرف الشخصي الخاص بك للحصول على معلوماتك\n"
        "أو اختر من القائمة ماذا تريد \n",
        reply_markup=get_main_menu(user_id)
    )

async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("يرجى كتابة الأمر بهذا الشكل:\n/check 12345678")
        return
    user_id = context.args[0]
    await send_info_by_id(update, user_id, with_menu=False)

async def send_info_by_id(update: Update, user_id: str, with_menu=True):
    try:
        df = pd.read_excel(DATA_FILE)
        row = df[df['ID'].astype(str) == str(user_id)]
        if not row.empty:
            info = row.iloc[0].to_dict()
            reply = "\n".join([f"{key}: {value}" for key, value in info.items()])
        else:
            reply = "لم يتم العثور على معلومات بهذا المعرف الشخصي."
    except Exception as e:
        reply = f"حدث خطأ أثناء قراءة البيانات: {e}"

    if with_menu:
        await update.message.reply_text(reply, reply_markup=get_main_menu(update.message.from_user.id))
    else:
        await update.message.reply_text(reply)

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("ليس لديك صلاحية إرسال البث.")
        return

    if not context.args:
        await update.message.reply_text("يرجى كتابة رسالة الإرسال بعد الأمر /broadcast")
        return

    message = " ".join(context.args)
    subscribers = load_subscribers()
    success_count, fail_count = 0, 0
    failed_users = []

    for uid in subscribers:
        try:
            await context.bot.send_message(chat_id=int(uid), text=message)
            success_count += 1
        except Exception as e:
            fail_count += 1
            failed_users.append((uid, str(e)))

    report = f"✅ تم إرسال الرسالة إلى {success_count} مشترك(ين).\n❌ فشل الإرسال إلى {fail_count}.\n"
    if failed_users:
        report += "\nالأخطاء:\n" + "\n".join(f"- {uid}: {err}" for uid, err in failed_users)
    await update.message.reply_text(report)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    save_subscriber(user_id)

    text = update.message.text.strip()
    if text.isdigit():
        await send_info_by_id(update, text, with_menu=False)
    else:
        await update.message.reply_text(
            "الرجاء إرسال رقم المعرف الشخصي فقط أو استخدم القائمة.",
            reply_markup=get_main_menu(user_id)
        )

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("ليس لديك صلاحية رفع الملفات.")
        return

    document = update.message.document
    if not document.file_name.endswith(('.xlsx', '.xls')):
        await update.message.reply_text("يرجى رفع ملف Excel بصيغة xlsx أو xls فقط.")
        return

    file_path = os.path.join(os.getcwd(), DATA_FILE)
    file = await document.get_file()
    await file.download_to_drive(file_path)

    try:
        df = pd.read_excel(file_path)
        if 'ID' not in df.columns:
            df['ID'] = None
        df = generate_unique_ids(df)
        df.to_excel(file_path, index=False)
        await update.message.reply_text("✅ تم تحديث البيانات وتوليد المعرفات بنجاح.")
    except Exception as e:
        await update.message.reply_text(f"❌ حدث خطأ أثناء معالجة الملف: {e}")

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    save_subscriber(user_id)
    await update.message.reply_text("اختر من القائمة:", reply_markup=get_main_menu(user_id))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    if query.data == 'send_id':
        await query.message.reply_text("يرجى إرسال رقم المعرف الشخصي الخاص بك الآن.")
    elif query.data == 'help':
        await query.message.reply_text(
            "أرسل رقم المعرف الشخصي للحصول على معلوماتك.\n"
            "أو استخدم الأمر /check 12345678.\n"
            "للمساعدة اتصل بشركة الغيث: +963 938 724 493"
        )
    elif query.data == 'upload_file':
        await query.message.reply_text("يرجى إرسال ملف Excel الآن.") if user_id == ADMIN_ID else \
            await query.message.reply_text("ليس لديك صلاحية رفع الملفات.")
    elif query.data == 'broadcast':
        await query.message.reply_text("أرسل الأمر:\n/broadcast نص الرسالة") if user_id == ADMIN_ID else \
            await query.message.reply_text("ليس لديك صلاحية الإرسال.")
    elif query.data == 'reset_ui':
        if user_id == ADMIN_ID:
            chat_id = query.message.chat.id
            for i in range(1, 51):
                try:
                    await context.bot.delete_message(chat_id=chat_id, message_id=query.message.message_id - i)
                except:
                    continue
            await context.bot.send_message(
                chat_id=chat_id,
                text="✅ تم تنظيف الواجهة.\nاختر من القائمة:",
                reply_markup=get_main_menu(user_id)
            )
        else:
            await query.message.reply_text("ليس لديك صلاحية استخدام هذا الزر.")

if __name__ == '__main__':
    TOKEN = "8185399272:AAGATkqVDOlym1p_BEJc1Feqjza1yzaNnwY"  # ← استبدله بتوكن البوت الخاص بك
    bot = Bot(TOKEN)
    bot.delete_webhook()
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("check", check))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.Document.ALL & ~filters.COMMAND, handle_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("✅ Bot is running...")
    app.run_polling()
