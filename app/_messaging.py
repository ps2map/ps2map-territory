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
# NOTE: Have to type callback arguments as Any as the actual messages will
# have subtypes which would violate LSP
Callback = typing.Callable[[typing.Any], _Coro | None]

_log = logging.getLogger('app.messaging')


class MessagingComponent:
    """Base class for message-based application components.

    External callers can subscribe to messages using the
    :meth:`subscribe` method. The :meth:`dispatch` method can be used
    by subclasses to send messages to all subscribers of that
    particular message type.

    Any logging messages are sent to the ``app.messaging`` logger.
    """

    def __init__(self) -> None:
        self.__subscriptions: dict[str, list[Callback]] = {}

    def dispatch(self, event: str, payload: typing.Any) -> None:
        """Dispatch a payload to all subscribers of that message type.

        This method is intended to be called by subclasses or other
        external components, the latter is primarily useful for
        mocking and unit testing.

        Any exceptions in the dispatched callbacks will be logged and
        ignored. If you need to handle exceptions, wrap the exceptional
        parts of the callback itself.

        :param event: The message type to dispatch.
        :param payload: The message payload to dispatch.
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError as err:
            raise RuntimeError('dispatch requires event loop') from err

        subs_notified = 0
        for callback in self.__subscriptions.get(event, []):

            # Catch-all for exceptions in callbacks to avoid escalating
            # them to the dispatching code
            try:
                if asyncio.iscoroutinefunction(callback):
                    loop.create_task(callback(payload))
                else:
                    loop.call_soon_threadsafe(callback, payload)
            except Exception as err:
                _log.exception('error dispatching message: %s', err)
            else:
                subs_notified += 1

        _log.debug('dispatched message to %d subscribers', subs_notified)

    def subscribe(self, event: str, callback: Callback) -> None:
        """Add a message subscription.

        Any time a message with the given type is dispatched, the
        given callback will be invoked via the asyncio event loop. The
        callback may be a coroutine function or a regular function.

        :param event: The message type to subscribe to.
        :param callback: The callback to invoke.
        """
        try:
            subs = self.__subscriptions[event]
        except KeyError:
            subs = self.__subscriptions[event] = []
        if callback not in subs:
            subs.append(callback)
        else:
            _log.info('ignoring duplicate subscription for message type: %s',
                      event)

    def unsubscribe(self, event: str, callback: Callback) -> bool:
        """Remove a message subscription.

        Removes a callback from the list of subscribers for the given
        message type. If none are found, no error is raised, but False
        is returned instead.

        :param event: The message type to unsubscribe from.
        :param callback: The callback to remove.
        :return: True if the callback was found and removed, False
            otherwise.
        """
        try:
            subs = self.__subscriptions[event]
        except KeyError:
            return False
        try:
            subs.remove(callback)
        except ValueError:
            return False
        return True

    def unsubscribe_all(self, event: str) -> int:
        """Remove all message subscriptions for a given message type.

        :param event: The message type to unsubscribe from.
        :return: The number of subscriptions removed.
        """
        return len(self.__subscriptions.pop(event, []))
