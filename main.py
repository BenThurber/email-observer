# coding=utf-8
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


class _Config:
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


def sleepUnless(timeout_s, abortSleepCondition):
    for _ in range(timeout_s):
        time.sleep(1)
        if abortSleepCondition():
            break


def decodeMimeText(s):
    mimeTextEncodingTuples = email.header.decode_header(s)
    return ' '.join(
        (m[0].decode(m[1]) if m[1] is not None else (m[0].decode('utf-8') if hasattr(m[0], 'decode') else str(m[0])))
        for m in mimeTextEncodingTuples)


# This is the threading object that does all the waiting on
# the event
class IMAPClientManager(object):
    def __init__(self, imap_client, sync_callback: callable):
        self.thread = threading.Thread(target=self.idle)
        self.imap_client = imap_client
        self.event = threading.Event()
        self.needsReset = threading.Event()
        self.needsResetExc = None
        self.sync_callback = sync_callback

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
                self.imap_client.idle(callback=callback)
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
                self.do_sync()

    # The method that gets called when a new email arrives.
    # Replace it with something better.
    def do_sync(self):  # Gets triggered on new email event, but also periodically without (?) email events
        self.sync_callback()


class GracefulKiller:
    kill_now = False

    def __init__(self):
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)

    def exit_gracefully(self, signum, frame):
        logging.info("Caught kill signal: {}".format(signum))
        self.kill_now = True


class EmailObserver:
    def __init__(self, mailbox='Inbox'):
        self.mailbox = mailbox

        self.imapClientManager = None
        self.imapClient = None
        self.killer = GracefulKiller()
        self.observers = []

        self._prev_email_timestamp = "Sat, 01 Jan 2000 00:00:00 +0000"
        self._prev_email_timestamp_temp_new = None

    def register_observer(self, observer):
        # ToDo WIP
        self.observers.append(observer)

    def start(self):
        while True:
            try:
                try:
                    imap_client = imaplib2.IMAP4_SSL(config.IMAP_SERVER)
                    imap_client.login(config.EMAIL_USER, config.EMAIL_PASSWORD)
                    imap_client.select(self.mailbox)  # We need to get out of the AUTH state, so we just select the INBOX.
                    imapClientManager = IMAPClientManager(imap_client, self.fetch_newest_emails)  # Start the Idler thread
                    imapClientManager.start()
                    logging.info('IMAP listening has started')

                    # Helps update the timestamp, so that on event only new emails are sent with notifications
                    self.fetch_newest_emails()

                    while not self.killer.kill_now and not imapClientManager.needsReset.is_set():
                        time.sleep(1)

                    if imapClientManager.needsReset.is_set():
                        raise imapClientManager.needsResetExc  # raises instance of imaplib2.IMAP4.abort
                    elif self.killer.kill_now:
                        break
                finally:
                    if self.imapClientManager is not None:
                        self.imapClientManager.stop()  # Had to do this stuff in a try-finally, since some testing went a little wrong.
                        self.imapClientManager.join()
                    if self.imapClient is not None:
                        self.imapClient.close()
                        self.imapClient.logout()  # This is important!
                    logging.info('IMAP listening has stopped, conn cleanup was run for: Listener: {}, Client: {}'
                                 .format(self.imapClientManager is not None, self.imapClient is not None))
                    sys.stdout.flush()  # probably not needed
            except imaplib2.IMAP4.abort as e:
                retryDelay_s = 1
                sleepUnless(retryDelay_s, lambda: self.killer.kill_now)
                if self.killer.kill_now:
                    break
            except socket.gaierror as e:
                logging.error(f"Failed to connect to IMAP server: {e}")
                break

    def fetch_newest_emails(self):
        try:
            mail = imaplib2.IMAP4_SSL(config.IMAP_SERVER)
            mail.login(config.EMAIL_USER, config.EMAIL_PASSWORD)
            mail.select(self.mailbox)

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

            if self._prev_email_timestamp_temp_new is not None:
                self._prev_email_timestamp = self._prev_email_timestamp_temp_new
                self._prev_email_timestamp_temp_new = None

        except (imaplib2.IMAP4.error, socket.gaierror) as e:
            logging.error(f"Failed to connect to IMAP server: {e}")


if __name__ == '__main__':
    # Create a logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    # Create formatter and add it to the handler
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    console_handler.setFormatter(formatter)

    # Add the handler to the logger
    logger.addHandler(console_handler)


    e = EmailObserver()
    e.start()
