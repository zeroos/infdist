import ns.core


def schedule(time, callback):
    ns.core.Simulator.Schedule(
        ns.core.Seconds(time), callback,
    )


def stop(time=None):
    if time is None:
        ns.core.Simulator.Stop()
    else:
        schedule(time, lambda: stop())


def run():
    ns.core.Simulator.Run()
    ns.core.Simulator.Destroy()


def now():
    """ Returns simulation time in ns, as integer """
    return int(ns.core.Simulator.Now().GetInteger())


def now_float():
    """ Returns simulation time in s, as float """
    return now()/10**9
