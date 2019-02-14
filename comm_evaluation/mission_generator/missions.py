import numpy as np

from .models import MessageSet, Message

BATTERY_DATA_TYPE = 'batt'
POSITION_DATA_TYPE = 'position'


def generate_periodic_messages(
    t_end, agents_num, data_type, t_start=0, f=1, data_f=lambda t: {}
):
    return MessageSet(t_end, [
        Message(
            agent_id,
            set(range(agents_num)) - set([agent_id]),
            t,
            data_type,
            data_f(t)
        )
        for agent_id in range(agents_num)
        for t in np.arange(t_start, t_end, 1/f)
    ])


def generate_batt_messages(t_end, agents_num, t_start=0, f=1,
                           level_start=1, level_end=0):

    def batt_level(t):
        a = (level_start - level_end) / (t_start - t_end)
        b = level_end - a * t_end
        level = a*t+b
        return {
            'batt_level': level,
        }

    return generate_periodic_messages(
        t_end, agents_num, BATTERY_DATA_TYPE, t_start, f, batt_level
    )


def generate_pos_messages(t_end, agents_num, t_start=0, f=5):
    return generate_periodic_messages(
        t_end, agents_num, POSITION_DATA_TYPE, t_start, f
    )


def generate_simple_3D_reconstruction(
    t_end,
):
    agents_num = 5

    batt_msgs = generate_batt_messages(t_end, agents_num)
    pos_msgs = generate_pos_messages(t_end, agents_num)

    # status_msgs = generate_status_messages(t_end)
    # objective_msgs = generate_objective_messages(t_end)
    # map_msgs = generate_map_messages(t_end)

    return batt_msgs + pos_msgs


if __name__ == "__main__":
    msgs = generate_simple_3D_reconstruction(22)
    print(msgs.__str__(
        ['sender', 'receivers', 't_sent', 'data', 'data_type']))