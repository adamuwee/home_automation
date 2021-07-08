import asyncio
from datetime import time
import logging
import threading

class async_timer(threading.Thread):
    def __init__(self, logger, interval, first_immediately, timer_name, context, callback):
        threading.Thread.__init__(self)
        self._logger = logger
        self._interval = interval
        self._first_immediately = first_immediately
        self._name = timer_name
        self._context = context
        self._callback = callback
        self._is_first_call = True
        self._ok = True
        #self._task = asyncio.ensure_future(self._job())
        #self._task = asyncio.create_task(self._job())
        self._logger.info(f'{timer_name} timer init done')
        self.run()

    async def _job(self):
        try:
            while self._ok:
                if not self._is_first_call or not self._first_immediately:
                    await asyncio.sleep(self._interval)
                await self._callback(self._name, self._context, self)
                self._is_first_call = False
        except Exception as ex:
            self._logger.info(ex)

    def run(self):
        try:
            while self._ok:
                self._callback(self._name, self._context, self)
                time.sleep(self._interval)
        except Exception as ex:
            self._logger.info(ex)

    def cancel(self):
        self._ok = False
        self._task.cancel()

async def some_callback(timer_name, context, timer):
    context['count'] += 1
    self._logger.info('callback: ' + timer_name + ", count: " + str(context['count']))

    if timer_name == 'Timer 2' and context['count'] == 3:
        timer.cancel()
        self._logger.info(timer_name + ": goodbye and thanks for all the fish")

def main():
    timer1 = async_timer(interval=1, first_immediately=True, timer_name="Timer 1", context={'count': 0}, callback=some_callback)
    timer2 = async_timer(interval=5, first_immediately=False, timer_name="Timer 2", context={'count': 0}, callback=some_callback)

    try:
        loop = asyncio.get_event_loop()
        loop.run_forever()
    except KeyboardInterrupt:
        timer1.cancel()
        timer2.cancel()
        print("clean up done")
    pass

if __name__ == "__main__":
    main()