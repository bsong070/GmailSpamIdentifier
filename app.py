from flask import Flask, render_template, request
import os
from email.header import decode_header
from datetime import datetime, timedelta
import tensorflow as tf
from tensorflow.keras.preprocessing.text import Tokenizer
from tensorflow.keras.preprocessing.sequence import pad_sequences
import imaplib
import email
from email.header import decode_header

app = Flask(__name__)


@app.route("/", methods=["GET", "POST"])
def index():
    show_popup = False 

    if request.method == "POST":
        username = request.form["email"]
        password = request.form["password"]
        try:
            mail = imaplib.IMAP4_SSL("imap.gmail.com")
            mail.login(username, password)
            mail.select("inbox")

            one_month_ago = datetime.now() - timedelta(days=30)

            target_date = datetime.now()  
            since_date = one_month_ago
            imap_since_date = since_date.strftime("%d-%b-%Y").upper()

            search_criteria = f'SINCE "{imap_since_date}"'

            status, email_data = mail.uid("search", None, search_criteria)
            uids = email_data[0].split()
            emails = []

            for uid in uids:
                status, msg_data = mail.uid("fetch", uid, "(RFC822)")
                msg = email.message_from_bytes(msg_data[0][1])

                subject_bytes, encoding = decode_header(msg["Subject"])[0]
                if isinstance(subject_bytes, bytes):
                    subject = subject_bytes.decode(encoding or "utf-8")
                else:
                    subject = str(subject_bytes)

                email_body = ""
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        try:
                            email_body = part.get_payload(
                                decode=True).decode("utf-8")
                        except UnicodeDecodeError:
                            email_body = part.get_payload(
                                decode=True).decode("latin1")
                        break  # Stop at the first text/plain part

                email_body = ' '.join(email_body.split())
                emails.append(' '.join([subject, email_body]))

            loaded_model = tf.keras.models.load_model('best_model.h5')

            max_sequence_length = 5916

            tokenizer = Tokenizer()
            tokenizer.fit_on_texts(emails)
            email_text_seqs = tokenizer.texts_to_sequences(emails)
            email_text_padded = pad_sequences(
                email_text_seqs, padding='post', maxlen=max_sequence_length)

            spam_threshold = 0.1

            # List to store spam classification results
            email_classifications = []

            predicted_probs = loaded_model.predict(email_text_padded)

            # Loop through the predicted probabilities and classify emails
            for i, predicted_prob in enumerate(predicted_probs):
                subject = emails[i]  
                email_date = msg["Date"]
                uid = uids[i]  

                # Classify as spam or not spam
                is_spam = predicted_prob >= spam_threshold

                email_classifications.append({
                    "subject": subject,
                    "body": email_body,  
                    "date": email_date,
                    "is_spam": is_spam,
                    "predicted_prob": predicted_prob * 100,
                    "msg_id": uid
                })

            # Create a spam folder if it doesn't exist
            spam_folder_name = "Spam"
            result, data = mail.list()
            if f"{spam_folder_name} " not in data[0].decode():
                mail.create(spam_folder_name)

            mail.select("inbox")

            # Loop through the email classifications and move spam emails to the spam folder
            for email_classification in email_classifications:
                if email_classification["is_spam"]:
                    msg_id = email_classification["msg_id"]
                    uid = msg_id

                    status, email_data = mail.uid("fetch", uid, "(RFC822)")

                    copy_result = mail.uid("COPY", uid, spam_folder_name)
      
            mail.close()
            mail.logout()
        except Exception as e:
            show_popup = True

    return render_template("index.html", show_popup=show_popup)


if __name__ == "__main__":
    app.run(debug=True, port=9001)
