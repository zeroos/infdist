import plotly.graph_objs as go
import plotly.io as pio
from datetime import datetime

from .trial import TreeTrial


class BaseExperiment:
    DEBUG_NONE = 0
    DEBUG_PROGRESS = 1
    DEBUG_ALL = 2

    def __init__(self, agents_num, t_end):
        self.agents_num = agents_num
        self.t_end = t_end
        self.trial_cls = TreeTrial
        self._example_trial = None

    def prepare_trial(self, trial_cls=None):
        if trial_cls is None:
            trial_cls = self.trial_cls
        t = trial_cls(self.agents_num, self.t_end)
        return t

    def progress(self, percent, debug, start_time=None):
        if debug >= self.DEBUG_PROGRESS:
            p = percent/100
            if start_time and percent != 0:
                duration = (datetime.now()-start_time)
                total = duration/p
                to_go = (
                    total-duration
                )
                eta = datetime.now() + to_go
            else:
                eta = '?'
                to_go = '?'
            print('  {:.2f}% ETA: {} (in {})'.format(
                percent, eta, to_go,
            ), end='\r')

    def run(self, debug=DEBUG_NONE):
        t = self.prepare_trial()
        t.run()
        self.result = t

    def print_result(self):
        self.result.print_stats()

    def get_graphs(self):
        return {}

    def get_graph_title(self, graph_name):
        return graph_name

    def get_graph_xaxis_title(self, graph_name):
        return "todo"

    def get_graph_yaxis_title(self, graph_name):
        return "todo"

    def _set_figure_layout(self, graph_name, figure):
        figure.update_layout(
            title=self.get_graph_title(graph_name),
            xaxis_title=self.get_graph_xaxis_title(graph_name),
            yaxis_title=self.get_graph_yaxis_title(graph_name),
        )

    def save_graphs(self, f=None):
        for graph_name, graph in self.get_graphs().items():
            fig = go.Figure({'data': graph, 'title': "test"})
            self._set_figure_layout(graph_name, fig)
            pio.write_image(fig, '/tmp/{}.pdf'.format(graph_name))
            if f is not None:
                pio.write_image(fig, f.format(graph_name))