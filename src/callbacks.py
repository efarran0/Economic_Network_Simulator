"""
Dash Callback Module for Interactive Economy Simulation

This module registers callbacks for a Dash web app that simulates an economic network.
It allows users to:
- Start/stop simulations
- Dynamically update system state over time
- Visualize system matrix and time series of key economic parameters (alpha and rho)
- Identify and display anomalies in economic dynamics

Main functionalities:
- Initializes an `EconomyNetwork` object upon simulation start
- Steps the model forward in time based on a Dash interval component
- Visualizes the evolving state as a heatmap and a dual-axis time series plot
- Displays outlier detections for alpha and rho

Requirements:
- Dash
- Plotly
- NumPy
- `EconomyNetwork` class from `src.sim`
"""

import json
import numpy as np
from dash import Input, Output, State, callback_context, no_update
from dash.exceptions import PreventUpdate
import plotly.graph_objs as go
from plotly.subplots import make_subplots
from src.sim import EconomyNetwork


def register_callbacks(app):
    """
    Register Dash callbacks for controlling the simulation and updating the interface.

    Parameters:
    - app (Dash): The Dash app instance on which to register the callbacks.
    """

    @app.callback(
        Output('screen', 'data'),
        Output('econ-store', 'data'),
        Output('interval-update', 'disabled'),
        Output('matrix-graph', 'figure'),
        Output('propensity-graph', 'figure'),
        Output('alpha-output', 'value'),
        Output('rho-output', 'value'),
        Input('start_btn', 'n_clicks'),
        Input('stop_btn', 'n_clicks'),
        Input('interval-update', 'n_intervals'),
        Input('alpha-output', 'value'),
        Input('rho-output', 'value'),
        State('screen', 'data'),
        State('econ-store', 'data'),
        State('s_h_input', 'value'),
        State('s_f_input', 'value'),
        State('alpha_input', 'value'),
        State('rho_input', 'value'),
        State('sens_input', 'value'),
        State('mem_input', 'value'),
        prevent_initial_call=True
    )
    def control_and_update(start_clicks, stop_clicks, n_intervals, alpha_slider, rho_slider,
                           screen, econ_data, s_h, s_f, alpha_input, rho_input, sens, mem_input):
        """
        Main callback for controlling simulation and updating UI.

        Handles:
        - Initialization of the EconomyNetwork object on 'Start'
        - Disabling simulation and UI on 'Stop'
        - Advancing the simulation and updating visualizations on interval ticks or slider change

        Returns:
        - Updated screen state
        - Serialized EconomyNetwork system state
        - Interval enabled/disabled
        - Matrix heatmap figure
        - Alpha/Rho dual time series plot
        - Updated alpha/rho values
        """

        ctx = callback_context
        if not ctx.triggered:
            raise PreventUpdate

        trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]

        if trigger_id == 'start_btn':
            # Initialize a new simulation
            econ = EconomyNetwork([s_h, s_f], [alpha_input, rho_input], sens, mem_input)
            data = json.dumps(econ.sys)
            empty_fig = go.Figure()
            return 'sim', data, False, empty_fig, empty_fig, alpha_input, rho_input

        elif trigger_id == 'stop_btn':
            # Stop simulation and return to set up screen
            return 'setup', no_update, True, no_update, no_update, no_update, no_update

        elif trigger_id in ['interval-update', 'alpha-output', 'rho-output'] and screen == 'sim':
            if not econ_data:
                raise PreventUpdate

            # Deserialize the system state and reinstantiate the model
            sys = json.loads(econ_data)
            econ = EconomyNetwork([0, 0], [0.5, 0.5], sens, mem_input)
            econ.sys = {int(k): v for k, v in sys.items()}

            # Optional manual overrides from sliders
            alpha_override = alpha_slider if trigger_id == 'alpha-output' else None
            rho_override = rho_slider if trigger_id == 'rho-output' else None

            # Advance simulation
            econ.step(alpha_override=alpha_override, rho_override=rho_override)

            t = max(econ.sys.keys())
            if alpha_override is not None:
                econ.sys[t]['alpha'] = alpha_override
            if rho_override is not None:
                econ.sys[t]['rho'] = rho_override

            # Extract last N steps for plotting
            t_vals = [x - max(econ.sys.keys()) for x in econ.sys.keys()]
            alpha_vals = [round(v['alpha'], 2) for v in econ.sys.values()]
            rho_vals = [round(v['rho'], 2) for v in econ.sys.values()]
            t_plot = t_vals[-mem_input:]
            alpha_plot = alpha_vals[-mem_input:]
            rho_plot = rho_vals[-mem_input:]

            # --- Create Heatmap of current matrix ---
            matrix = econ.get_matrix()
            labels = np.array([['s_h', 'c'], ['w', 's_f']])
            fig1 = go.Figure(data=go.Heatmap(
                z=matrix,
                x=['households', 'firms'],
                y=['households', 'firms'],
                colorscale=[[0.0, "#d4a373"], [0.5, "#e6b566"], [1.0, "#fbeec1"]],
                text=labels,
                texttemplate="%{text}",
                hovertemplate="%{z}<extra></extra>",
                textfont={"size": 16, "color": "red"},
                zmin=0,
                zmax=1
            ))
            fig1.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
            fig1.update_yaxes(autorange="reversed")

            # --- Create Combined Time Series Plot with Outliers ---
            fig_combined = make_subplots(rows=1, cols=2, column_widths=[0.7, 0.3], horizontal_spacing=0.05)

            # Time series traces
            fig_combined.add_trace(go.Scatter(x=t_plot, y=alpha_plot, name='α', mode='lines'), row=1, col=1)
            fig_combined.add_trace(go.Scatter(x=t_plot, y=rho_plot, name='ρ', mode='lines'), row=1, col=1)

            fig_combined.update_xaxes(
                title_text='t',
                dtick=1,
                tickvals=t_plot,
                ticktext=[str("") if v != 0 else "now" for v in t_plot],
                range=[min(t_plot), max(t_plot)],
                row=1, col=1
            )
            fig_combined.update_yaxes(title_text='Value', range=[0, 1], row=1, col=1)

            # Vertical markers
            fig_combined.add_trace(
                go.Scatter(x=[1] * len(alpha_plot), y=alpha_plot, mode='markers',
                           marker=dict(color='blue', size=5), name='α'), row=1, col=2)
            fig_combined.add_trace(
                go.Scatter(x=[2] * len(rho_plot), y=rho_plot, mode='markers',
                           marker=dict(color='red', size=5), name='ρ'), row=1, col=2)

            fig_combined.update_xaxes(
                range=[0.5, 2.5], tickvals=[1, 2], ticktext=['α', 'ρ'],
                showgrid=False, zeroline=False, showticklabels=True, row=1, col=2
            )
            fig_combined.update_yaxes(
                title_text='', range=[0, 1],
                showgrid=False, showticklabels=False, row=1, col=2
            )

            # Reference lines
            fig_combined.add_shape(type='line', x0=1, x1=1, y0=0, y1=1,
                                   line=dict(color='blue', width=1, dash='dash'), row=1, col=2)
            fig_combined.add_shape(type='line', x0=2, x1=2, y0=0, y1=1,
                                   line=dict(color='red', width=1, dash='dash'), row=1, col=2)

            # Add outlier legend symbol (hidden point)
            fig_combined.add_trace(
                go.Scatter(x=[None], y=[None], mode='markers',
                           marker=dict(color='firebrick', size=12, symbol='star'),
                           name='Outlier'), row=1, col=1
            )

            # Highlight outliers
            alpha_outliers = econ.sys[t]['outliers']['alpha']
            rho_outliers = econ.sys[t]['outliers']['rho']

            for i, is_out in enumerate(alpha_outliers):
                if is_out:
                    fig_combined.add_trace(
                        go.Scatter(x=[t_plot[i]], y=[alpha_plot[i]], mode='markers',
                                   marker=dict(color='firebrick', size=12, symbol='star'),
                                   showlegend=False), row=1, col=1)
                    fig_combined.add_trace(
                        go.Scatter(x=[1], y=[alpha_plot[i]], mode='markers',
                                   marker=dict(color='firebrick', size=12, symbol='star'),
                                   showlegend=False), row=1, col=2)

            for i, is_out in enumerate(rho_outliers):
                if is_out:
                    fig_combined.add_trace(
                        go.Scatter(x=[t_plot[i]], y=[rho_plot[i]], mode='markers',
                                   marker=dict(color='firebrick', size=12, symbol='star'),
                                   showlegend=False), row=1, col=1)
                    fig_combined.add_trace(
                        go.Scatter(x=[2], y=[rho_plot[i]], mode='markers',
                                   marker=dict(color='firebrick', size=12, symbol='star'),
                                   showlegend=False), row=1, col=2)

            fig_combined.update_layout(
                title_text="Historical propensity data", title_x=0.5,
                plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
                showlegend=True, height=500
            )
            fig_combined['data'][2]['showlegend'] = False
            fig_combined['data'][3]['showlegend'] = False

            return screen, json.dumps(econ.sys), False, fig1, fig_combined, alpha_vals[-1], rho_vals[-1]

        else:
            raise PreventUpdate

    @app.callback(
        Output('setup-screen', 'style'),
        Output('sim-screen', 'style'),
        Input('screen', 'data')
    )
    def toggle_screens(screen):
        """
        Callback to toggle visibility between setup and simulation screens.

        Parameters:
        - screen (str): Screen state identifier ('setup' or 'sim').

        Returns:
        - Two dictionaries for Dash component styles.
        """
        if screen == 'setup':
            return {'display': 'block'}, {'display': 'none'}
        elif screen == 'sim':
            return {'display': 'none'}, {'display': 'block'}
        else:
            return no_update, no_update
