import pandas as pd
import dhnx
import dhnx.plotting
import dhnx.network
import dhnx.optimization.oemof_heatpipe as heatpipe
import dhnx.optimization.optimization_models as optimization
import oemof.solph as solph
import os
import logging
from program_files.preprocessing.components.district_heating_calculations import *
from program_files.preprocessing.components.district_heating_clustering import *

# create an empty thermal network
thermal_net = dhnx.network.ThermalNetwork()


def concat_on_thermal_net_components(comp_type: str, new_dict: dict,
                                     thermal_net) -> None:
    """
    outsourced the concatenation which is part of several algorithm
    steps
    
    :param comp_type: defines on which thermal net components DataFrame\
        the new dict will be appended
    :type comp_type: str
    :param new_dict: holds the information of the new component to be \
        appended on an existing DataFrame
    :type new_dict: dict
    :param thermal_net: TODO
    :type thermal_net: dhnx.network.ThermalNetwork
    """
    # create consumers forks pandas Dataframe for thermal network
    thermal_net.components[comp_type] = pd.concat(
        [thermal_net.components[comp_type],
         pd.DataFrame([pd.Series(data=new_dict)])]
    )
    
    
def clear_thermal_net():
    """
    Method used to clear the pandas dataframes of thermal network
    that might consist of old information.
    """
    for i in ["forks", "consumers", "pipes", "producers"]:
        thermal_net.components[i] = pd.DataFrame()


def create_fork(point: list, label: int, thermal_net, bus=None):
    """
    Outsourced from creation algorithm to reduce redundancy.

    :param point: list containing information of the point to be
                  appended
    :type point: list
    :param label: id of the fork to be created
    :type label: int
    :param bus: bus is used for producers forks identification
    :type bus: str
    """
    fork_dict = {
        "id": label,
        "lat": point[1],
        "lon": point[2],
        "component_type": "Fork",
        "street": point[5],
        "t": point[4],
    }
    if bus:
        fork_dict.update({"bus": bus})
    concat_on_thermal_net_components("forks", fork_dict, thermal_net)


def append_pipe(from_node: str, to_node: str, length: float, street: str,
                thermal_net):
    """
    method which is used to append the heatpipeline specified by the
    methods parameter to the list of pipes
    (thermal_net.components["pipes"])
    
    :param from_node: definition of the first edge of the \
        heatpipeline to be appended to the list of pipes
    :type from_node: str
    :param to_node: definition of the second edge of the \
        heatpipeline to be appended to the list of pipes
    :type from_node: str
    :param length: definition of the length of the heatpipeline to \
        be appended to the list of pipes
    :type length: float
    :param street: defintion of the street in which the \
        heatpipeline will be layed
    :type street: str
    :param thermal_net: TODO
    :type thermal_net: dhnx.network.ThermalNetwork
    """
    pipe_dict = {
        "id": "pipe-{}".format(len(thermal_net.components["pipes"]) + 1),
        "from_node": from_node,
        "to_node": to_node,
        "length": length,
        "component_type": "Pipe",
        "street": street,
    }
    concat_on_thermal_net_components("pipes", pipe_dict, thermal_net)


def remove_redundant_sinks(oemof_opti_model: optimization.OemofInvestOptimizationModel):
    """
        Within the dhnx algorithm empty sinks are created,
        which are removed in this method.

        :param oemof_opti_model: dh model
        :type oemof_opti_model: optimization.OemofInvestOptimizationModel
        :return: **oemof_opti_model** \
            (optimization.OemofInvestOptimizationModel) - dh model \
            without unused sinks
    """
    sinks = []
    # get demand created bei dhnx and add them to the list "sinks"
    for i in range(len(oemof_opti_model.nodes)):
        if "demand" in str(oemof_opti_model.nodes[i]):
            sinks.append(i)
    # delete the created sinks
    already_deleted = 0
    for sink in sinks:
        oemof_opti_model.nodes.pop(sink - already_deleted)
        already_deleted += 1
    # return the oemof model without the unused sinks
    return oemof_opti_model


def create_connection_points(consumers, road_sections):
    """
    Create the entries for the connection points and adds them to
    thermal network forks, consumers and pipes.

    :param consumers: holding nodes_data["sinks"]
    :type consumers: pandas.Dataframe
    :param road_sections: holding nodes_data["district heating"]
    :type road_sections: pandas.Dataframe
    """
    consumer_counter = 0
    for num, consumer in consumers[consumers["active"] == 1].iterrows():
        if consumer["district heating conn."] == 1:
            # TODO label of sinks has to be id_...
            label = consumer["label"].split("_")[0] + "1"
            foot_point = get_nearest_perp_foot_point(
                consumer, road_sections, consumer_counter, "consumers"
            )
            # add consumer to thermal network components (dummy
            # because cut from system after creating dhnx components
            concat_on_thermal_net_components(
                "consumers",
                {
                    "id": "consumers-{}".format(consumer_counter),
                    "lat": float(consumer["lat"]),
                    "lon": float(consumer["lon"]),
                    "component_type": "Consumer",
                    "P_heat_max": 1,
                    "input": consumer["label"],
                    "label": consumer["label"],
                    "street": foot_point[5],
                },
                thermal_net
            )
            # add fork of perpendicular foot point to the dataframe
            # of forks
            create_fork(foot_point, foot_point[0][10:-5], thermal_net)
            # add pipe between the perpendicular foot point and the
            # building to the dataframe of pipes
            append_pipe(
                "forks-{}".format(foot_point[0][10:-5]),
                foot_point[0][:-5],
                foot_point[3],
                label,
                thermal_net
            )
            consumer_counter += 1
            logging.info("\t Connected {} to district heating network".format(label))


def create_intersection_forks(street_sec: pd.DataFrame) -> None:
    """
    Creates the forks of the scenario given street points.

    :param street_sec: pandas Dataframe containing the street
                          sections beginning and ending points
    :type street_sec: pandas.Dataframe
    """
    road_section_points = {}
    fork_num = len(thermal_net.components["forks"])
    # create a dictionary containing all street points once
    for num, street in street_sec[street_sec["active"] == 1].iterrows():
        for i in ["1st", "2nd"]:
            if [
                street["lat. {} intersection".format(i)],
                street["lon. {} intersection".format(i)],
            ] not in road_section_points.values():
                road_section_points.update(
                    {
                        "forks-{}".format(fork_num): [
                            street["lat. {} intersection".format(i)],
                            street["lon. {} intersection".format(i)],
                        ]
                    }
                )
                fork_num += 1
            
    # append all points on forks dataframe
    for point in road_section_points:
        concat_on_thermal_net_components(
            "forks",
            {
                "id": point[6:],
                "lat": road_section_points[point][0],
                "lon": road_section_points[point][1],
                "component_type": "Fork",
            },
            thermal_net
        )


def create_producer_connection_point(nodes_data: pd.DataFrame, road_sections):
    """
    create the entries for the producers  connection points and adds
    them to thermal network forks, producers and pipes

    :param nodes_data:
    :type nodes_data: pandas.Dataframe
    :param road_sections: Dataframe containing the street sections
                          start and end points
    :type road_sections: pandas.Dataframe
    """
    number = 0
    for i, bus in nodes_data["buses"].iterrows():
        if bus["district heating conn."] == "dh-system" and bus["active"] == 1:
            # create a producer buses and its connections point and pipe
            # due to the given lat and lon from buses sheet
            concat_on_thermal_net_components(
                "producers",
                {
                    "id": number,
                    "lat": bus["lat"],
                    "lon": bus["lon"],
                    "component_type": "Producer",
                    "active": 1,
                },
                thermal_net
            )
            foot_point = get_nearest_perp_foot_point(
                bus, road_sections, number, "producers"
            )
            create_fork(
                foot_point, len(thermal_net.components["forks"]) + 1,
                thermal_net, bus["label"]
            )
            append_pipe(
                "producers-{}".format(number),
                "forks-{}".format(len(thermal_net.components["forks"])),
                foot_point[3],
                bus["label"],
                thermal_net
            )
            number += 1
            logging.info(
                "\t Connected {} to district heating network".format(bus["label"])
            )


def create_supply_line(streets):
    """
    Acquisition of all points of a route (road sections), order
    itself in ascending order and creation of the lines to link the
    forks.

    :param streets: district heating Dataframe including the
        scenario sheet
    :type streets: pandas.Dataframe
    """
    pipes = {}
    for num, street in streets[streets["active"] == 1].iterrows():
        road_section = []
        for key, point in thermal_net.components["forks"].iterrows():
            if (
                point["lat"] == street["lat. 1st intersection"]
                and point["lon"] == street["lon. 1st intersection"]
            ):
                # check if begin of road section is begin or end of another
                road_section.append(
                    [
                        point["id"],
                        street["lat. 1st intersection"],
                        street["lon. 1st intersection"],
                        0,
                        0.0,
                        street["label"],
                    ]
                )
            if (
                point["lat"] == street["lat. 2nd intersection"]
                and point["lon"] == street["lon. 2nd intersection"]
            ):
                # check if begin of road section is begin or end of another
                road_section.append(
                    [
                        point["id"],
                        street["lat. 2nd intersection"],
                        street["lon. 2nd intersection"],
                        0,
                        1.0,
                        street["label"],
                    ]
                )
            if "street" in point:
                if point["street"] == street["label"]:
                    road_section.append(
                        [
                            point["id"],
                            point["lat"],
                            point["lon"],
                            0,
                            point["t"],
                            street["label"],
                        ]
                    )

        # Order Connection points on the currently considered road section
        pipes.update({street["label"]: calc_street_lengths(road_section)})

    for street in pipes:
        for pipe in pipes[street]:
            ends = pipe[0].split(" - ")
            if "fork" in ends[0] and "consumers" in ends[0]:
                ends[0] = "forks-{}".format(ends[0][10:-5])
            else:
                ends[0] = "forks-{}".format(ends[0])
            if "fork" in ends[1] and "consumers" in ends[1]:
                ends[1] = "forks-{}".format(ends[1][10:-5])
            else:
                ends[1] = "forks-{}".format(ends[1])
            append_pipe(ends[0], ends[1], pipe[1], street, thermal_net)


def adapt_dhnx_style():
    """
    Brings the created pandas Dataframes to the dhnx style.
    """
    for i, p in thermal_net.components["consumers"].iterrows():
        if "consumers" in str(p["id"]):
            thermal_net.components["consumers"].replace(
                to_replace=p["id"], value=p["id"][10:], inplace=True
            )
    for i, p in thermal_net.components["pipes"].iterrows():
        if type(p["id"]) != int:
            thermal_net.components["pipes"].replace(
                to_replace=p["id"], value=p["id"][5:], inplace=True
            )
    thermal_net.components["consumers"].index = thermal_net.components["consumers"][
        "id"
    ]
    thermal_net.components["forks"].index = thermal_net.components["forks"]["id"]
    thermal_net.components["pipes"].index = thermal_net.components["pipes"]["id"]
    thermal_net.components["producers"].index = thermal_net.components["producers"][
        "id"
    ]


def create_components(nodes_data, anergy_or_exergy):
    """
    Runs dhnx methods for creating thermal network oemof components.

    :param nodes_data: Dataframe holing scenario sheet information
    :type nodes_data: pd.Dataframe
    :param anergy_or_exergy: bool which defines rather the considered \
        network is an exergy net (False) or an anergy net (True)
    :type anergy_or_exergy: bool

    :return: **oemof_opti_model** (dhnx.optimization) - model \
        holding dh components
    """
    frequency = nodes_data["energysystem"]["temporal resolution"].values
    start_date = str(nodes_data["energysystem"]["start date"].values[0])
    # changes names of data columns,
    # so it fits the needs of the feedinlib
    name_dc = {"min. investment capacity": "cap_min",
               "max. investment capacity": "cap_max",
               "periodical costs": "capex_pipes",
               "fix investment costs": "fix_costs",
               "periodical constraint costs": "periodical_constraint_costs",
               "fix investment constraint costs": "fix_constraint_costs"}
    nodes_data["pipe types"] = nodes_data["pipe types"].rename(columns=name_dc)
      
    # set standard investment options that do not require user modification
    invest_opt = {
        "consumers": {
            "bus": pd.DataFrame(
                {"label_2": "heat",
                 "active": 1,
                 "excess": 0,
                 "shortage": 0}, index=[0]
            ),
            "demand": pd.DataFrame(
                {"label_2": "heat", "active": 1, "nominal_value": 1}, index=[0]
            ),
        },
        "producers": {
            "bus": pd.DataFrame(
                {
                    "Unnamed: 0": 1,
                    "label_2": "heat",
                    "active": 1,
                    "excess": 0,
                    "shortage": 0,
                },
                index=[0],
            ),
            "source": pd.DataFrame({"label_2": "heat", "active": 0}, index=[0]),
        },
        "network": {
            "pipes": nodes_data["pipe types"].loc[(nodes_data["pipe types"]["anergy_or_exergy"] == ("anergy" if anergy_or_exergy else "exergy")) & (nodes_data["pipe types"]["distribution_pipe"] == 1)],
            "pipes_houses": nodes_data["pipe types"].loc[(nodes_data["pipe types"]["anergy_or_exergy"] == ("anergy" if anergy_or_exergy else "exergy")) & (nodes_data["pipe types"]["building_pipe"] == 1)],
        },
    }
    # start dhnx algorithm to create dh components
    oemof_opti_model = optimization.setup_optimise_investment(
        thermal_network=thermal_net,
        invest_options=invest_opt,
        num_ts=nodes_data["energysystem"]["periods"],
        start_date=(
            str(start_date[9:10])
            + "/"
            + str(start_date[6:7])
            + "/"
            + str(start_date[0:4])
        ),
        bidirectional_pipes=True,
        frequence=(str(frequency[0])).upper(),
        label_5="anergy" if anergy_or_exergy else "exergy"
    )
    return oemof_opti_model


def calc_heat_pipe_attributes(oemof_opti_model, anergy_or_exergy, nodes_data):
    for a in oemof_opti_model.nodes:
        if str(type(a)) == "<class 'oemof.solph.network.bus.Bus'>":
            pass
        else:
            label = a.label.tag3	
            if int(nodes_data["pipe types"].loc[
                       nodes_data["pipe types"]["label_3"] == label][
                       "nonconvex"]) == 0:
                ep_costs = getattr(
                    a.outputs[list(a.outputs.keys())[0]].investment, "ep_costs"
                )
                length = ep_costs / float(
                    nodes_data["pipe types"].loc[
                        nodes_data["pipe types"]["label_3"] == label][
                        "capex_pipes"]
                )
                setattr(
                        a.outputs[list(a.outputs.keys())[0]].investment,
                        "periodical_constraint_costs",
                        length
                        * float(
                            nodes_data["pipe types"].loc[
                                nodes_data["pipe types"]["label_3"] == label][
                                "periodical_constraint_costs"
                            ]
                    ),
                )
            else:
                fix_costs = getattr(
                    a.outputs[list(a.outputs.keys())[0]].investment, "offset"
                )
                length = fix_costs / float(
                    nodes_data["pipe types"].loc[
                        nodes_data["pipe types"]["label_3"] == label][
                        "fix_costs"]
                )
                
            setattr(
                    a.outputs[list(a.outputs.keys())[0]].investment,
                    "periodical_constraint_costs",
                    length
                    * float(
                            nodes_data["pipe types"].loc[
                                nodes_data["pipe types"]["label_3"] == label][
                                "periodical_constraint_costs"
                            ]
                    ),
            )
            setattr(
                    a.outputs[list(a.outputs.keys())[0]].investment,
                    "fix_constraint_costs",
                    length
                    * float(
                            nodes_data["pipe types"].loc[
                                nodes_data["pipe types"]["label_3"] == label][
                                "fix_constraint_costs"
                            ]
                    ),
            )
            
            setattr(a.inputs[list(a.inputs.keys())[0]], "emission_factor", 0)
            setattr(a.outputs[list(a.outputs.keys())[0]], "emission_factor", 0)
            
    return oemof_opti_model


def connect_dh_to_system(oemof_opti_model, busd, nodes_data):
    """
        Method which creates links to connect the scenario based
        created sinks to the thermal network components created before.

        :param oemof_opti_model: Oemof model holing thermal network
        :type oemof_opti_model:
        :param busd: dictionary containing scenario buses
        :type busd: dict
        :return: - **oemof_opti_model** (dhnx.optimization) - oemof dh \
            model within connection to the main model
    """
    oemof_opti_model = remove_redundant_sinks(oemof_opti_model)
    oemof_opti_model = calc_heat_pipe_attributes(oemof_opti_model, False,
                                                 nodes_data)
    
    # create link to connect consumers heat bus to the dh-system
    for num, consumer in thermal_net.components["consumers"].iterrows():
        
        label = heatpipe.Label("consumers", "heat", "bus",
                               "consumers-{}".format(consumer["id"]), "exergy")
        
        inputs = {oemof_opti_model.buses[label]: solph.Flow(emission_factor=0)}
        
        outputs = {
            busd[consumer["input"]]: solph.Flow(
                investment=solph.Investment(
                    ep_costs=float(
                        nodes_data["pipe types"].loc[nodes_data["pipe types"]["label_3"] == "dh_heatstation"]["capex_pipes"]),
                    periodical_constraint_costs=float(
                        nodes_data["pipe types"].loc[nodes_data["pipe types"]["label_3"] == "dh_heatstation"][
                            "periodical_constraint_costs"]),
                    minimum=0,
                    maximum=999 * len(consumer["input"]),
                    existing=0,
                    nonconvex=False,
                    fix_constraint_costs=0,
                ),
                emission_factor=0,
            )}
        
        conversion_factors = {
            (label, busd[consumer["input"]]): float(
                nodes_data["pipe types"].loc[nodes_data["pipe types"]["label_3"] =="dh_heatstation"]["efficiency"])
        }
        
        oemof_opti_model.nodes.append(
            solph.Transformer(
                label=("dh_heat_house_station_"
                       + consumer["label"].split("_")[0]),
                inputs=inputs,
                outputs=outputs,
                conversion_factors=conversion_factors
            )
        )
        
    return oemof_opti_model


def connect_anergy_to_system(oemof_opti_model, busd, nodes_data):
    """
        Method which creates links to connect the scenario based
        created sinks to the thermal network components created before.

        :param oemof_opti_model: Oemof model holing thermal network
        :type oemof_opti_model:
        :param busd: dictionary containing scenario buses
        :type busd: dict
        :return: - **oemof_opti_model** (dhnx.optimization) - oemof dh \
            model within connection to the main model
    """
    import oemof.thermal.compression_heatpumps_and_chillers as cmpr_hp_chiller

    oemof_opti_model = remove_redundant_sinks(oemof_opti_model)
    oemof_opti_model = calc_heat_pipe_attributes(oemof_opti_model, True,
                                                 nodes_data)

    # create link to connect consumers heat bus to the dh-system
    for num, consumer in thermal_net.components["consumers"].iterrows():
        # TODO Temperaturen? from pre scenario
        # calculation of COPs with set parameters
        cops_hp = cmpr_hp_chiller.calc_cops(
                temp_high=168 * [60],
                temp_low=168 * [20],
                quality_grade=0.6,
                temp_threshold_icing=2,
                factor_icing=1,
                mode="heat_pump",
        )
        
        label = heatpipe.Label("consumers", "heat", "bus",
                               "consumers-{}".format(consumer["id"]), "anergy")
        # TODO elec bus
        inputs = {busd["ID_electricity_bus"]: solph.Flow(emission_factor=0),
                  oemof_opti_model.buses[label]: solph.Flow(emission_factor=0)}
    
        outputs = {
            busd[consumer["input"]]: solph.Flow(
                    investment=solph.Investment(
                            ep_costs=float(
                                nodes_data["pipe types"].loc["anergy_heat_pump"][
                                        "costs"]),
                            periodical_constraint_costs=float(
                                nodes_data["pipe types"].loc["anergy_heat_pump"][
                                        "constraint costs"]),
                            minimum=0,
                            maximum=999 * len(consumer["input"]),
                            existing=0,
                            nonconvex=False,
                            fix_constraint_costs=0,
                    ),
                    emission_factor=0,
            )}
    
        conversion_factors = {
            oemof_opti_model.buses[label]: [
                ((cop - 1) / cop) / 1 for cop in cops_hp],
            busd["ID_electricity_bus"]: [1 / cop for cop in cops_hp]
        }
    
        oemof_opti_model.nodes.append(
                solph.Transformer(
                        label=("anergy_heat_pump_"
                               + consumer["label"].split("_")[0]),
                        inputs=inputs,
                        outputs=outputs,
                        conversion_factors=conversion_factors
                )
        )

    return oemof_opti_model


def add_excess_shortage_to_dh(
    oemof_opti_model: optimization.OemofInvestOptimizationModel, nodes_data, busd
):
    """
        With the help of this method, it is possible to map an external
        heat supply (e.g. from a neighboring heat network) or the export
        to a neighboring heat network.

        :param oemof_opti_model: dh network components
        :type oemof_opti_model: optimization.OemofInvestOptimizationModel
        :param nodes_data: Dataframe containing all components data
        :type nodes_data: pandas. Dataframe
        :param busd: dict containing all buses of the energysystem under
         investigation
        :type busd: dict
        :return: - **oemof_opti_model** \
            (optimization.OemofInvestOptimizationModel) - dh network \
            components + excess and shortage bus
    """
    busses = []
    for i, bus in nodes_data["buses"].iterrows():
        if (
            bus["district heating conn."] != 0
            and bus["active"] == 1
            and bus["district heating conn."] != "dh-system"
        ):
            busses.append(bus)
    for bus in busses:
        if bus["district heating conn."] not in [0, 1]:
            conn_point = bus["district heating conn."].split("-")
            lat = None
            lon = None
            for i, street in nodes_data["district heating"].iterrows():
                if street["active"]:
                    if street["label"] == conn_point[0]:
                        if conn_point[1] == "1":
                            lat = street["lat. 1st intersection"]
                            lon = street["lon. 1st intersection"]
                        elif conn_point[1] == "2":
                            lat = street["lat. 2nd intersection"]
                            lon = street["lon. 2nd intersection"]
                        else:
                            raise ValueError("invalid district heating conn.")
            if lat is None or lon is None:
                raise ValueError
            for key, fork in thermal_net.components["forks"].iterrows():
                if fork["lat"] == lat and fork["lon"] == lon:
                    oemof_opti_model.nodes.append(
                        solph.custom.Link(
                            label=(
                                "link-dhnx-" + bus["label"] + "-f{}".format(fork["id"])
                            ),
                            inputs={
                                oemof_opti_model.buses[
                                    heatpipe.Label(
                                        "infrastructure",
                                        "heat",
                                        "bus",
                                        str("forks-{}".format(fork["id"])),
                                    )
                                ]: solph.Flow(),
                                busd[bus["label"]]: solph.Flow(),
                            },
                            outputs={
                                busd[bus["label"]]: solph.Flow(),
                                oemof_opti_model.buses[
                                    heatpipe.Label(
                                        "infrastructure",
                                        "heat",
                                        "bus",
                                        str("forks-{}".format(fork["id"])),
                                    )
                                ]: solph.Flow(),
                            },
                            conversion_factors={
                                (
                                    oemof_opti_model.buses[
                                        heatpipe.Label(
                                            "infrastructure",
                                            "heat",
                                            "bus",
                                            str("forks-{}".format(fork["id"])),
                                        )
                                    ],
                                    busd[bus["label"]],
                                ): 1,
                                (
                                    busd[bus["label"]],
                                    oemof_opti_model.buses[
                                        heatpipe.Label(
                                            "infrastructure",
                                            "heat",
                                            "bus",
                                            str("forks-{}".format(fork["id"])),
                                        )
                                    ],
                                ): 1,
                            },
                        )
                    )

    return oemof_opti_model


def create_producer_connection(oemof_opti_model, busd, test):
    """
        This method creates a link that connects the heat producer to
        the heat network.

        :param oemof_opti_model: dh model created before
        :type oemof_opti_model:
        :param busd: dictionary containing the energysystem busses
        :type busd: dict
        :return: - **oemof_opti_model** (dhnx.optimization) - dhnx model \
            within the new Transformers
    """
    counter = 0
    for key, producer in thermal_net.components["forks"].iterrows():
        if str(producer["bus"]) != "nan":
            label = heatpipe.Label(
                "producers", "heat", "bus", str("producers-{}".format(str(counter))), "anergy" if test else "exergy"
            )
            oemof_opti_model.nodes.append(
                solph.Transformer(
                    label=(str(producer["bus"]) + "_dh_source_link_" + ("anergy" if test else "exergy")),
                    inputs={busd[producer["bus"]]: solph.Flow(emission_factor=0)},
                    outputs={
                        oemof_opti_model.buses[label]: solph.Flow(emission_factor=0)
                    },
                    conversion_factors={
                        (oemof_opti_model.buses[label], busd[producer["bus"]]): 1
                    },
                )
            )
            counter += 1

    return oemof_opti_model


def create_connect_dhnx(nodes_data, busd, clustering=False,
                        anergy_or_exergy=False):
    """
    At this point, the preparations of the heating network to use
    the dhnx package are completed. For this purpose, it is checked
    whether the given data result in a coherent network, which can
    be optimized in the following.

    :param nodes_data: Dataframe containing all components data
    :type nodes_data: pandas.Dataframe
    :param busd: dictionary containing scenario buses
    :type busd: dict
    :param clustering: used to define rather the spatial clustering
        algorithm is used or not
    """
    thermal_net.is_consistent()
    thermal_net.set_timeindex()
    # create components of district heating system
    oemof_opti_model = create_components(nodes_data, anergy_or_exergy)
    if clustering:
        connect_clustered_dh_to_system(oemof_opti_model, busd)
    else:
        # connect non dh and dh system using links to represent losses
        if anergy_or_exergy:
            connect_anergy_to_system(oemof_opti_model, busd, nodes_data)
        else:
            connect_dh_to_system(oemof_opti_model, busd, nodes_data)
    # remove dhnx flows that are not used due to deletion of sinks
    for i in range(len(oemof_opti_model.nodes)):
        outputs = oemof_opti_model.nodes[i].outputs.copy()
        for j in outputs.keys():
            if "consumers" in str(j) and "heat" in str(j) and "demand" in str(j):
                oemof_opti_model.nodes[i].outputs.pop(j)

    oemof_opti_model = \
        add_excess_shortage_to_dh(oemof_opti_model, nodes_data, busd)
    oemof_opti_model = \
        create_producer_connection(oemof_opti_model, busd, anergy_or_exergy)
    return oemof_opti_model.nodes


def create_dh_map(result_path):
    import matplotlib.pyplot as plt
    static_map = dhnx.plotting.StaticMap(thermal_net)
    static_map.draw(background_map=False)
    plt.title("Given network")
    components = {
        "forks": [thermal_net.components.forks, "tab:grey"],
        "consumers": [thermal_net.components.consumers,
                      "tab:green"],
        "producers": [thermal_net.components.producers,
                      "tab:red"]
    }
    for i in components:
        plt.scatter(
                components[i][0]["lon"],
                components[i][0]["lat"],
                color=components[i][1],
                label=i,
                zorder=2.5,
                s=50)
    plt.text(-2, 32, "P0", fontsize=14)
    plt.text(82, 0, "P1", fontsize=14)
    plt.legend()
    plt.savefig(result_path + "/district_heating.jpeg")
    

def district_heating(
    nodes_data, nodes, busd, district_heating_path, result_path, cluster_dh,
    anergy_or_exergy
):
    """
    The district_heating method represents the main method of heat
    network creation, it is called by the main algorithm to perform
    the preparation to use the dhnx components and finally add them
    to the already existing energy system. It is up to the users to
    choose whether they want to use spatial clustering or not.

    :param nodes_data: Dataframe containing the scenario data
    :type nodes_data: pandas.Dataframe
    :param nodes: list which contains the already created components
    :type nodes: list
    :param busd: dictionary containing the scenario buses
    :type busd: dict
    :param district_heating_path: Path to a folder in which the
        calculated heat network information was stored after a
        one-time connection point search. Entering this parameter in
        the GUI shortens the calculation time, because the above
        mentioned search can then be skipped.
    :type district_heating_path: str
    :param result_path: path where the result will be saved
    :type result_path: str
    :param cluster_dh: boolean which defines rather the heat network
        is clustered spatially or not
    :type cluster_dh: bool
    :param anergy_or_exergy: bool which defines rather the considered \
        network is an exergy net (False) or an anergy net (True)
    :type anergy_or_exergy: bool
    """
    clear_thermal_net()
    dh = False
    # check rather saved calculation are distributed
    if district_heating_path == "":
        # check if the scenario includes district heating
        if len(nodes_data["district heating"]) != 0:
            street_sections = convert_dh_street_sections_list(
                nodes_data["district heating"].copy()
            )
            # create pipes and connection point for building-streets connection
            create_connection_points(nodes_data["buses"], street_sections)
            # appends the intersections to the thermal network forks
            create_intersection_forks(nodes_data["district heating"])
            # create pipes and connection point for producer-streets connection
            create_producer_connection_point(nodes_data, street_sections)
            # create supply line laid on the road
            create_supply_line(nodes_data["district heating"])
            # if any consumers where connected to the thermal network
            if thermal_net.components["consumers"].values.any():
                adapt_dhnx_style()
                # save the created dataframes to improve runtime of a
                # second optimization run
                for i in ["consumers", "pipes", "producers", "forks"]:
                    thermal_net.components[i].to_csv(result_path
                                                     + "/" + i + ".csv")

                create_dh_map(result_path)
                dh = True
    else:
        for i in ["consumers", "pipes", "producers", "forks"]:
            thermal_net.components[i] = pd.read_csv(
                district_heating_path + "/" + i + ".csv"
            )
        adapt_dhnx_style()
        dh = True
        if cluster_dh:
            clustering_dh_network(nodes_data)
        for i in ["consumers", "pipes", "producers", "forks"]:
            thermal_net.components[i].to_csv(result_path + "/" + i + ".csv")
    if dh:
        if cluster_dh == 1:
            new_nodes = create_connect_dhnx(nodes_data, busd, True,
                                            anergy_or_exergy)
        else:
            new_nodes = create_connect_dhnx(nodes_data, busd, False,
                                            anergy_or_exergy)
        for i in new_nodes:
            nodes.append(i)
    return nodes
