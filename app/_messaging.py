"""Base class for message-based applications."""

import asyncio
import collections.abc
import logging
import typing

__all__ = [
    'Callback',
    'MessagingComponent',
]

_Coro = collections.abc.Coroutine[None, None, None]
Callback = typing.Callable[[tuple[typing.Any, ...]], _Coro | None]

_log = logging.getLogger('messaging')


class MessagingComponent:
    """Base class for message-based application components.

    External callers can subscribe to messages using the
    :meth:`subscribe` method. The :meth:`emit` method can be used by
    subclasses to send messages to all subscribers of that particular
    topic.

    Any logging messages are sent to the `messaging` logger.
    """

    def __init__(self) -> None:
        self.__subscriptions: dict[str, list[Callback]] = {}

    def emit(self, topic: str, payload: typing.Any) -> None:
        """Dispatch a payload to all subscribers of the given topic.

        This method is intended to be called by subclasses or other
        external components, the latter is primarily useful for
        mocking and unit testing.

        Any exceptions in the dispatched callbacks will be logged and
        ignored. If you need to handle exceptions, wrap the exceptional
        parts of the callback itself.

        :param topic: Topic under which to emit the given payload.
        :param payload: The message payload to dispatch.
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError as err:
            raise RuntimeError('dispatch requires event loop') from err

        subs_notified = 0
        for callback in self.__subscriptions.get(topic, []):

            # Catch-all for exceptions in callbacks to avoid escalating
            # them to the dispatching code
            try:
                if asyncio.iscoroutinefunction(callback):
                    loop.create_task(callback(payload))
                else:
                    loop.call_soon_threadsafe(callback, payload)
            except Exception as err:
                if isinstance(err, KeyboardInterrupt):
                    raise
                _log.exception('exception ignored in callback for topic %s:',
                               topic, err)
            else:
                subs_notified += 1

        _log.debug('dispatched payload for topic %s to %d subscribers',
                   topic, subs_notified)

    def subscribe(self, topic: str, callback: Callback) -> None:
        """Add a message subscription.

        Any time a message with the given type is dispatched, the
        given callback will be invoked via the asyncio event loop. The
        callback may be a coroutine function or a regular function.

        :param topic: Topic under which to emit the given payload.
        :param callback: The callback to invoke when a message is
            dispatched under the given topic.
        """
        try:
            subs = self.__subscriptions[topic]
        except KeyError:
            subs = self.__subscriptions[topic] = []
        if callback not in subs:
            subs.append(callback)
        else:
            _log.info('ignoring duplicate subscription for message type: %s',
                      topic)

    def unsubscribe(self, topic: str, callback: Callback) -> bool:
        """Remove a message subscription.

        Removes a callback from the list of subscribers for the given
        message type. If none are found, no error is raised, but False
        is returned instead.

        :param topic: Topic under which the callback is registered.
        :param callback: The callback to remove.
        :return: True if the callback was found and removed, False
            otherwise.
        """
        try:
            subs = self.__subscriptions[topic]
        except KeyError:
            return False
        try:
            subs.remove(callback)
        except ValueError:
            return False
        return True

    def unsubscribe_all(self, topic: str) -> int:
        """Remove all message subscriptions for a given message type.

        :param topic: Topic whose subscriptions should be removed.
        :return: The number of subscriptions removed.
        """
        return len(self.__subscriptions.pop(topic, []))
