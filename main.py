import logging
import os
import time
from collections import defaultdict
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

# توكن البوت الخاص بك من BotFather
TOKEN = os.environ["BOT_TOKEN"]

# آيدي المالك الوحيد المسموح له بالرفع
OWNER_ID = 806070128

# تتبع الرسائل لحساب الـ Spam: {chat_id: {sender_id: [timestamps]}}
user_media_tracker = defaultdict(lambda: defaultdict(list))

# قائمة المشرفين الذين تم رفعهم بواسطة البوت: {chat_id: {user_ids}}
promoted_by_bot = defaultdict(set)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

async def promote_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """رفع العضو الذي يتم الرد على رسالته كمشرف بدون أي صلاحيات"""
    if not update.effective_user or not update.effective_chat or not update.message:
        return

    sender_id = update.effective_user.id
    chat_id = update.effective_chat.id

    # التحقق من أن الآيدي هو المالك فقط
    if sender_id != OWNER_ID:
        return

    # التحقق مما إذا كان الأمر رداً (Reply) على رسالة شخص آخر
    if not update.message.reply_to_message or not update.message.reply_to_message.from_user:
        await update.message.reply_text("⚠️ يجب الرد على رسالة العضو المراد رفعه مع كتابة (رفع مشرف).")
        return

    target_user = update.message.reply_to_message.from_user
    target_id = target_user.id

    text = update.message.text.strip()
    if text == "رفع مشرف":
        try:
            # رفع المشرف مع تعطيل جميع الصلاحيات بشكل صريح ومباشر
            await context.bot.promote_chat_member(
                chat_id=chat_id,
                user_id=target_id,
                is_anonymous=False,
                can_manage_chat=False,
                can_delete_messages=False,
                can_manage_video_chats=False,
                can_restrict_members=False,
                can_promote_members=False,
                can_change_info=False,
                can_invite_users=False,
                can_post_messages=False,
                can_edit_messages=False,
                can_pin_messages=False,
                can_manage_topics=False,
                can_post_stories=False,
                can_edit_stories=False,
                can_delete_stories=False
            )
            
            # حفظ الآيدي في قائمة المشرفين المرفوعين بالبوت لهذه المجموعة
            promoted_by_bot[chat_id].add(target_id)
            await update.message.reply_text(f"تم رفع العضو `{target_id}` (`{target_user.first_name}`) مشرفاً بدون أي صلاحيات بنجاح.", parse_mode='Markdown')
        except Exception as e:
            await update.message.reply_text(f"❌ خطأ من سيرفر تلجرام: {e}")

async def monitor_media_spam(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مراقبة إرسال الوسائط المتكررة في وقت قصير (3 وسائط بأقل من ثانيتين)"""
    message = update.message
    if not message:
        return

    chat_id = update.effective_chat.id
    current_time = time.time()

    # تحديد الهوية: إما قناة (sender_chat) أو مستخدم (from_user)
    if message.sender_chat:
        sender_key = f"channel_{message.sender_chat.id}"
        is_channel = True
    elif message.from_user:
        sender_key = f"user_{message.from_user.id}"
        is_channel = False
    else:
        return

    # تسجيل وقت إرسال الوسائط
    timestamps = user_media_tracker[chat_id][sender_key]
    timestamps.append(current_time)

    # الاحتفاظ فقط بالرسائل التي تمت خلال آخر ثانيتين (2.0 ثانية)
    timestamps = [t for t in timestamps if current_time - t <= 2.0]
    user_media_tracker[chat_id][sender_key] = timestamps

    # إذا تجاوز عدد الوسائط 3 أو أكثر خلال أقل من ثانيتين
    if len(timestamps) >= 3:
        if is_channel:
            # 1. حظر/منع القناة من إرسال الرسائل في المجموعة
            try:
                await context.bot.ban_chat_sender_chat(chat_id=chat_id, sender_chat_id=message.sender_chat.id)
            except Exception:
                pass

            # 2. تنزيل كافة المشرفين الذين تم رفعهم بواسطة البوت دون أي استثناء
            target_admins = list(promoted_by_bot[chat_id])
            for admin_id in target_admins:
                try:
                    await context.bot.promote_chat_member(
                        chat_id=chat_id,
                        user_id=admin_id,
                        is_anonymous=False,
                        can_manage_chat=False,
                        can_delete_messages=False,
                        can_manage_video_chats=False,
                        can_restrict_members=False,
                        can_promote_members=False,
                        can_change_info=False,
                        can_invite_users=False,
                        can_post_messages=False,
                        can_edit_messages=False,
                        can_pin_messages=False,
                        can_manage_topics=False,
                        can_post_stories=False,
                        can_edit_stories=False,
                        can_delete_stories=False
                    )
                except Exception:
                    pass
            
            # تفريغ القائمة بعد التنزيل
            promoted_by_bot[chat_id].clear()
            
            try:
                await message.reply_text("⚠️ تم اكتشاف تفجير وسائط عبر قناة! تم حظر القناة وتنزيل جميع المشرفين المرفوعين عن طريق البوت فوراً.")
            except Exception:
                pass
        else:
            # تنزيل/حظر الحساب الشخصي
            try:
                await context.bot.ban_chat_member(chat_id=chat_id, user_id=message.from_user.id)
                await message.reply_text("⚠️ تم حظر المستخدم لتكرار الوسائط بسرعة تتجاوز الحد المسموح.")
            except Exception:
                pass
            
        # إعادة تصفير السجل لهذا المرسل
        user_media_tracker[chat_id][sender_key] = []

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    # معالج أمر رفع مشرف (بالرد على الرسالة)
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'^رفع مشرف$'), promote_user))

    # معالج الوسائط (صور، فيديوهات، متحركة / GIF، إلخ)
    media_filter = filters.PHOTO | filters.VIDEO | filters.ANIMATION | filters.Document.ALL
    app.add_handler(MessageHandler(media_filter, monitor_media_spam))

    print("البوت يعمل الآن بكفاءة...")
    app.run_polling()

if __name__ == '__main__':
    main()
