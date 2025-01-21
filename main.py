# coding=utf-8
import io
import logging
import email
import email.parser
import email.header
import socket
import imaplib2
import threading
import sys
import time
import signal
from utilities import config_logging

config_logging("output.log")

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


class _Config:
    POP3_SERVER = None
    IMAP_SERVER = None
    EMAIL_USER = None
    EMAIL_PASSWORD = None
    EMAIL_SEARCH_DEPTH = None

    def __init__(self):
        for key in [a for a in dir(self) if not a.startswith('__') and not callable(getattr(self, a))]:
            import configVals_example
            getattr(configVals_example, key)  # Only to help remember to update the example config file

            import configVals
            setattr(self, key, getattr(configVals, key))


config = _Config()

prevEmailTimestamp = "Sat, 01 Jan 2000 00:00:00 +0000"
prevEmailTimestampTempNew = None


def decodeMimeText(s):
    mimeTextEncodingTuples = email.header.decode_header(s)
    return ' '.join(
        (m[0].decode(m[1]) if m[1] is not None else (m[0].decode('utf-8') if hasattr(m[0], 'decode') else str(m[0])))
        for m in mimeTextEncodingTuples)


def searchNewestEmail():
    global prevEmailTimestamp, prevEmailTimestampTempNew
    try:
        mail = imaplib2.IMAP4_SSL(config.IMAP_SERVER)
        mail.login(config.EMAIL_USER, config.EMAIL_PASSWORD)
        mail.select("inbox")

        result, data = mail.search(None, "ALL")
        email_ids = data[0].split()
        searchLimit = int(config.EMAIL_SEARCH_DEPTH)

        for i in reversed(email_ids[-searchLimit:]):
            result, msg_data = mail.fetch(i, "(RFC822)")
            raw_email = msg_data[0][1].decode("utf-8")
            message = email.message_from_string(raw_email)

            subject = decodeMimeText(message["Subject"])
            sender = decodeMimeText(message["From"])
            logging.info(f"<{sender}> {subject}")

        if prevEmailTimestampTempNew is not None:
            prevEmailTimestamp = prevEmailTimestampTempNew
            prevEmailTimestampTempNew = None

    except imaplib2.IMAP4.error as e:
        logging.error(f"Failed to connect to IMAP server: {e}")


# This is the threading object that does all the waiting on
# the event
class IMAPClientManager(object):
    def __init__(self, conn):
        self.thread = threading.Thread(target=self.idle)
        self.M = conn
        self.event = threading.Event()
        self.needsReset = threading.Event()
        self.needsResetExc = None

    def start(self):
        self.thread.start()

    def stop(self):
        # This is a neat trick to make thread end. Took me a
        # while to figure that one out!
        self.event.set()

    def join(self):
        self.thread.join()

    def idle(self):
        # Starting an unending loop here
        while True:
            # This is part of the trick to make the loop stop
            # when the stop() command is given
            if self.event.is_set():
                return
            self.needsync = False

            # A callback method that gets called when a new
            # email arrives. Very basic, but that's good.
            def callback(args):
                if not self.event.is_set():
                    self.needsync = True
                    self.event.set()

            # Do the actual idle call. This returns immediately,
            # since it's asynchronous.
            try:
                self.M.idle(callback=callback)
            except imaplib2.IMAP4.abort as exc:
                self.needsReset.set()
                self.needsResetExc = exc
            # This waits until the event is set. The event is
            # set by the callback, when the server 'answers'
            # the idle call and the callback function gets
            # called.
            self.event.wait()
            # Because the function sets the needsync variable,
            # this helps escape the loop without doing
            # anything if the stop() is called. Kinda neat
            # solution.
            if self.needsync:
                self.event.clear()
                self.dosync()

    # The method that gets called when a new email arrives.
    # Replace it with something better.
    def dosync(self):  # Gets triggered on new email event, but also periodically without (?) email events
        searchNewestEmail()


def sleepUnless(timeout_s, abortSleepCondition):
    for _ in range(timeout_s):
        time.sleep(1)
        if abortSleepCondition():
            break


class GracefulKiller:
    kill_now = False

    def __init__(self):
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)

    def exit_gracefully(self, signum, frame):
        logging.info("Caught kill signal: {}".format(signum))
        self.kill_now = True


imapClientManager = None
imapClient = None
killer = GracefulKiller()

while True:
    try:
        try:
            imapClient = imaplib2.IMAP4_SSL(config.IMAP_SERVER)
            imapClient.login(config.EMAIL_USER, config.EMAIL_PASSWORD)
            imapClient.select("INBOX")  # We need to get out of the AUTH state, so we just select the INBOX.
            imapClientManager = IMAPClientManager(imapClient)  # Start the Idler thread
            imapClientManager.start()
            logging.info('IMAP listening has started')

            # Helps update the timestamp, so that on event only new emails are sent with notifications
            searchNewestEmail()

            while not killer.kill_now and not imapClientManager.needsReset.is_set():
                time.sleep(1)

            if imapClientManager.needsReset.is_set():
                raise imapClientManager.needsResetExc  # raises instance of imaplib2.IMAP4.abort
            elif killer.kill_now:
                break
        finally:
            if imapClientManager is not None:
                imapClientManager.stop()  # Had to do this stuff in a try-finally, since some testing went a little wrong.
                imapClientManager.join()
            if imapClient is not None:
                imapClient.close()
                imapClient.logout()  # This is important!
            logging.info('IMAP listening has stopped, conn cleanup was run for: Listener: {}, Client: {}'
                  .format(imapClientManager is not None, imapClient is not None))
            sys.stdout.flush()  # probably not needed
    except imaplib2.IMAP4.abort as e:
        retryDelay_s = 1
        sleepUnless(retryDelay_s, lambda: killer.kill_now)
        if killer.kill_now:
            break
    except socket.gaierror as e:
        logging.error(f"Failed to connect to IMAP server: {e}")
        break
