# coding=utf-8
import os
import sys
import time
import email
import socket
import signal
import logging
import imaplib2
import threading
import email.parser
import email.header
from email.message import Message
from abc import ABC, abstractmethod


def sleep_unless(timeout_s, abort_sleep_condition):
    for _ in range(timeout_s):
        time.sleep(1)
        if abort_sleep_condition():
            break


def decode_mime_text(s):
    """Decodes a MIME-encoded string. This is used to decode email headers."""
    mime_text_encoding_tuples = email.header.decode_header(s)
    return ' '.join(
        (m[0].decode(m[1]) if m[1] is not None else (m[0].decode('utf-8') if hasattr(m[0], 'decode') else str(m[0])))
        for m in mime_text_encoding_tuples)


class EmailObserver(ABC):
    """This is an Abstract class which serves as an interface.  Any classes
    that wish to receive notifications of new emails can implement this class,
    possibly using multiple inheritance.  For example:

    class MyClass(MyClassSuperclass, EmailObserver):
        def on_mail_received(...):
            ...
    """
    @abstractmethod
    def on_mail_received(self, new_messages: list[Message], message_list: list[Message]):
        pass


# This is the threading object that does all the waiting on
# the event
class IMAPClientManager(object):
    """Manages the IMAP client and the IMAP idle loop"""
    def __init__(self, imap_client, sync_callback: callable):
        self.thread = threading.Thread(target=self.idle)
        self.imap_client = imap_client
        self.event = threading.Event()
        self.needs_reset = threading.Event()
        self.needs_reset_exc = None
        self.needs_sync = False
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
            self.needs_sync = False

            # A callback method that gets called when a new
            # email arrives. Very basic, but that's good.
            def callback(args):
                if not self.event.is_set():
                    self.needs_sync = True
                    self.event.set()

            # Do the actual idle call. This returns immediately,
            # since it's asynchronous.
            try:
                self.imap_client.idle(callback=callback)
            except imaplib2.IMAP4.abort as exc:
                self.needs_reset.set()
                self.needs_reset_exc = exc
            # This waits until the event is set. The event is
            # set by the callback, when the server 'answers'
            # the idle call and the callback function gets
            # called.
            self.event.wait()
            # Because the function sets the needs_sync variable,
            # this helps escape the loop without doing
            # anything if the stop() is called. Kinda neat
            # solution.
            if self.needs_sync:
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


class EmailNotifier:
    """This is the subject which maintains a list of observers.  When one or
    more emails are received, all observers are notified by calling their
    on_mail_received method."""
    def __init__(self, imap_server=None, email_user=None, email_password=None, message_list_len=10, mailbox='Inbox', imap_port=None, **kwargs):
        self._first = True
        self.imap_server = imap_server
        self.email_user = email_user
        self.email_password = email_password
        self.message_list_len = message_list_len
        self.mailbox = mailbox
        self.imap_port = imap_port

        # Load email server credentials from environment variables if not provided
        imap_server_env = kwargs.get("imap_server_env") or "EMAIL_OBSERVER_IMAP_SERVER"
        email_user_env = kwargs.get("email_user_env") or "EMAIL_OBSERVER_USER"
        email_password_env = kwargs.get("email_password_env") or "EMAIL_OBSERVER_PASSWORD"
        if not self.imap_server:
            self.imap_server = os.getenv(imap_server_env)
        if not self.email_user:
            self.email_user = os.getenv(email_user_env)
        if not self.email_password:
            self.email_password = os.getenv(email_password_env)
        if not all((self.imap_server, self.email_user, self.email_password)):
            raise EnvironmentError(
                "{}, {}, and {} must be set as environment variables, or values must be passed in as arguments to {} constructor.".format(
                    imap_server_env, email_user_env, email_password_env, self.__class__.__name__
                )
            )

        self.imapClientManager = None
        self.killer = GracefulKiller()
        self.observers = []
        self.prev_message_list_dict = {}
        self.prev_uids = set()

    def register_observer(self, observer: EmailObserver):
        if isinstance(observer, EmailObserver):
            self.observers.append(observer)
        else:
            raise TypeError(f"observer of type {observer.__class__.__name__} is not a subclass of EmailObserver.")

    def start(self):
        imap_client = None
        while True:
            try:
                try:
                    imap_client = imaplib2.IMAP4_SSL(self.imap_server, self.imap_port)
                    imap_client.login(self.email_user, self.email_password)
                    imap_client.select(self.mailbox)  # We need to get out of the AUTH state, so we just select the INBOX.
                    self.imapClientManager = IMAPClientManager(imap_client, self.fetch_newest_emails)  # Start the Idler thread
                    self.imapClientManager.start()
                    logging.info('IMAP listening has started')

                    # Helps update the timestamp, so that on event only new emails are sent with notifications
                    self.fetch_newest_emails()

                    while not self.killer.kill_now and not self.imapClientManager.needs_reset.is_set():
                        time.sleep(1)

                    if self.imapClientManager.needs_reset.is_set():
                        raise self.imapClientManager.needs_reset_exc  # raises instance of imaplib2.IMAP4.abort
                    elif self.killer.kill_now:
                        break
                finally:
                    if self.imapClientManager is not None:
                        self.imapClientManager.stop()  # Had to do this stuff in a try-finally, since some testing went a little wrong.
                        self.imapClientManager.join()
                    if imap_client is not None:
                        imap_client.close()
                        imap_client.logout()  # This is important!
                    logging.info('IMAP listening has stopped, conn cleanup was run for: Listener: {}, Client: {}'
                                 .format(self.imapClientManager is not None, imap_client is not None))
                    sys.stdout.flush()  # probably not needed
            except imaplib2.IMAP4.abort as e:
                retry_delay_s = 1
                sleep_unless(retry_delay_s, lambda: self.killer.kill_now)
                if self.killer.kill_now:
                    break
            except socket.gaierror as e:
                logging.error(f"Failed to connect to IMAP server: {e}")
                break

    def fetch_newest_emails(self):
        imap_client = None
        try:
            imap_client = imaplib2.IMAP4_SSL(self.imap_server, self.imap_port)
            imap_client.login(self.email_user, self.email_password)
            imap_client.select(self.mailbox)

            result, data = imap_client.uid('SEARCH', None, 'ALL')
            uids = data[0].split()
            all_uids = {int(b) for b in data[0].split()}

            uids_to_fetch = reversed([int(b) for b in data[0].split()[-self.message_list_len:]])

            message_list_dict = {uid: self.prev_message_list_dict.get(uid) or self.fetch_uid(imap_client, uid) for uid in uids_to_fetch}
            message_list = list(message_list_dict.values())

            if self._first:
                self._first = False
                new_messages = []
            else:
                new_uids = all_uids.difference(self.prev_uids)  # Should be very fast, even for a large mailbox.
                new_messages = [message_list_dict.get(uid) or self.fetch_uid(imap_client, uid) for uid in new_uids]

            # IDLE is triggered when the read status is changed on an email.
            # This check prevents observers from being notified.
            if message_list_dict.keys() == self.prev_message_list_dict.keys():
                return

            self.prev_message_list_dict = message_list_dict
            self.prev_uids = all_uids

            for observer in self.observers:
                observer.on_mail_received(new_messages, message_list)

        except (imaplib2.IMAP4.error, socket.gaierror) as e:
            logging.error(f"Failed to connect to IMAP server: {e}")

        finally:
            if imap_client is not None:
                imap_client.close()
                imap_client.logout()  # This is important!

    @staticmethod
    def fetch_uid(imap_client, uid: int) -> Message:
        """Fetches the email message with the given UID from the IMAP server."""
        if not isinstance(uid, int):
            raise TypeError(f"uid {uid} must be an integer, not {uid.__class__.__name__}")
        result, msg_data = imap_client.uid('FETCH', str(uid), '(RFC822)')
        # ToDo add error handling for non 'OK' result and None msg_data.
        raw_email = msg_data[0][1].decode("utf-8")
        message = email.message_from_string(raw_email)
        return message


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

    try:
        en = EmailNotifier()
        en.start()
    except EnvironmentError as _e:
        logging.error(_e)
