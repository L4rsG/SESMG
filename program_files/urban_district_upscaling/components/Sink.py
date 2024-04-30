"""
    Christian Klemm - christian.klemm@fh-muenster.de
    Gregor Becker - gregor.becker@fh-muenster.de
    Janik Budde - janik.budde@fh-muenster.de
"""
import pandas


def create_standard_parameter_sink(sink_type: str, label: str, sink_input: str,
                                   annual_demand: float, sheets: dict,
                                   standard_parameters: pandas.ExcelFile
                                   ) -> dict:
    """
        Creates a sink with standard_parameters, based on the standard
        parameters given in the "standard_parameters" dataset and adds
        it to the "sheets"-output dataset.
    
        :param sink_type: needed to get the standard parameters of the
                          link to be created
        :type sink_type: str
        :param label: label, the created sink will be given
        :type label: str
        :param sink_input: label of the bus which will be the input of \
            the sink to be created
        :type sink_input: str
        :param annual_demand: Annual demand previously calculated by \
            the method provided for the considered sink type, \
            representing the energy demand of the sink.
        :type annual_demand: float
        :param sheets: dictionary containing the pandas.Dataframes that\
                will represent the model definition's Spreadsheets
            :type sheets: dict
        :param standard_parameters: pandas imported ExcelFile \
                containing the non-building specific technology data
        :type standard_parameters: pandas.ExcelFile
        
        :return: - **sheets** (dict) - dictionary containing the \
            pandas.Dataframes that will represent the model \
            definition's Spreadsheets which was modified in this method
    """
    from program_files import create_standard_parameter_comp

    return create_standard_parameter_comp(
        specific_param={
            "label": label,
            "input": sink_input,
            "annual demand": annual_demand,
        },
        standard_parameter_info=[sink_type, "2_sinks", "sink type"],
        sheets=sheets,
        standard_parameters=standard_parameters
    )


def create_electricity_sink(building: pandas.Series, area: float, sheets: dict,
                            sinks_standard_param: pandas.DataFrame,
                            standard_parameters: pandas.ExcelFile) -> dict:
    """
        In this method, the electricity demand is calculated either on
        the basis of energy certificates (area-specific demand values)
        or on the basis of inhabitants. Using this calculated demand
        the load profile electricity sink is created.
        
        :param building: building specific data which were imported \
            from the US-Input sheet
        :type building: pandas.Series
        :param area: building gross area
        :type area: float
        :param sheets: dictionary containing the pandas.Dataframes that\
                will represent the model definition's Spreadsheets
        :type sheets: dict
        :param sinks_standard_param: sinks sheet from standard \
            parameter sheet
        :type sinks_standard_param: pandas.DataFrame
        :param standard_parameters: pandas imported ExcelFile \
                containing the non-building specific technology data
        :type standard_parameters: pandas.ExcelFile
        
        :return: - **sheets** (dict) - dictionary containing the \
            pandas.Dataframes that will represent the model \
            definition's Spreadsheets which was modified in this method
    """
    sink_param = standard_parameters.parse("2_2_electricity")
    specific_demands = {}
    # If an area-specific electricity requirement is given, e.g. from an
    # energy certificate, use the else clause.
    if not building["electricity demand"]:
        # if the investigated building is a residential building
        if building["building type"] in ["single family building",
                                         "multi family building"]:
            # get all columns from electricity sink parameters sheets
            # that begin with the building type
            for column in sink_param.columns:
                if building["building type"] in column:
                    specific_demands[column] = [sink_param.loc[1, column]]
            # specific electricity demand for less/equal 5 occupants in
            # one unit
            # calculation: specific demand from standard parameter * units
            if building["occupants per unit"] <= 5:
                # specific demand column from standard parameter sheet
                column = (building["building type"] + " "
                          + str(int(building["occupants per unit"]))
                          + " person")
                # demand calculation
                demand_el = specific_demands[column][0] * building["units"]
            # specific electricity demand for more than 5 occupants in
            # one unit
            # calculation:
            # specific demand =
            # (specific demand for 5 occupants per unit
            #   from standard parameter) / 5
            # occupants = total occupants of the investigated building
            # demand = specific demand * occupants
            else:
                # specific demand column from standard parameter sheet
                column = building["building type"] + " 5 person"
                # specific demand per occupant
                demand_el_specific = (specific_demands[column][0]) / 5
                # total occupants of the investigated building
                occupants = building["occupants per unit"] * building["units"]
                # demand calculation
                demand_el = demand_el_specific * occupants
        else:
            # specific demand per area
            demand_el_specific = sink_param.loc[1, building["building type"]]
            NFA_GFA = \
                sinks_standard_param.loc[
                    building["building type"] + " electricity sink"][
                    "net floor area / area"]
            demand_el = demand_el_specific * area * NFA_GFA
    else:
        demand_el = building["electricity demand"] * area
    
    return create_standard_parameter_sink(
        sink_type=building["building type"] + " electricity sink",
        label=str(building["label"]) + "_electricity_demand",
        sink_input=str(building["label"]) + "_electricity_bus",
        annual_demand=demand_el,
        sheets=sheets,
        standard_parameters=standard_parameters
    )


def create_share_sink_system(sheets, standard_parameters, sink_type, label, share_type, annual_demand):
    """
    
    """
    from .Bus import create_standard_parameter_bus
    from .Link import create_link
    
    # create the bus to which the wood stove and the wood stove
    # share sink will be attached
    sheets = create_standard_parameter_bus(
        label=label + "_" + share_type + "_heat_bus",
        sheets=sheets,
        standard_parameters=standard_parameters,
        bus_type="heat bus decentral")
    
    # create the sink for the amount of heat which has to be
    # produced by the wood stove
    sheets = create_standard_parameter_sink(
        sink_type=sink_type,
        label=label + "_" + share_type + "_heat_demand",
        sink_input=label + "_" + share_type + "_heat_bus",
        annual_demand=annual_demand,
        sheets=sheets,
        standard_parameters=standard_parameters
    )
    
    # connect the wood stove bus to the building heat bus by an
    # directed link so that solubility is still ensured in the
    # event of a possible shortfall due to the wood stove.
    sheets = create_link(
        label=label + "_" + share_type + "_heat_link",
        sheets=sheets,
        link_type="heat decentral link share decentral",
        standard_parameters=standard_parameters,
        bus_1=label + "_heat_bus",
        bus_2=label + "_" + share_type + "_heat_bus"
    )
    
    return sheets


def create_heat_sink(building: pandas.Series, area: float, sheets: dict,
                     sinks_standard_param: pandas.DataFrame,
                     standard_parameters: pandas.ExcelFile) -> dict:
    """
        In this method, the heat demand is calculated either on
        the basis of energy certificates (area-specific demand values)
        or on the basis of inhabitants. Using this calculated demand
        the load profile heat sink is created.

        :param building: building specific data which were imported \
            from the US-Input sheet
        :type building: pandas.Series
        :param area: building gross area
        :type area: float
        :param sheets: dictionary containing the pandas.Dataframes that\
                will represent the model definition's Spreadsheets
        :type sheets: dict
        :param sinks_standard_param: sinks sheet from standard \
            parameter sheet
        :type sinks_standard_param: pandas.DataFrame
        :param standard_parameters: pandas imported ExcelFile \
                containing the non-building specific technology data
        :type standard_parameters: pandas.ExcelFile
        
        :return: - **sheets** (dict) - dictionary containing the \
            pandas.Dataframes that will represent the model \
            definition's Spreadsheets which was modified in this method
    """
    # load the specific heat demands from standard parameter sheet
    standard_param = standard_parameters.parse("2_1_heat", na_filter=False)
    standard_param.set_index("year of construction", inplace=True)
    
    # year of construction: buildings older than 1918 are clustered in
    # <1918
    yoc = int(building["year of construction"])
    yoc = (yoc if yoc > 1918 else "<1918")
    
    # define a variable for building type
    building_type = building["building type"]
    
    # define component label
    sink_type = building_type + " heat sink"
    
    # If there is not an area-specific heat requirement given,
    # e.g. from an energy certificate, use the else clause.
    if not building["heat demand"]:
        # if the investigated building is a residential building
        if building_type in ["single family building",
                             "multi family building"]:
            # units: buildings bigger than 12 units are clustered in > 12
            units = int(building["units"])
            units = str(units) if units < 12 else "> 12"
            # specific demand per area
            specific_heat_demand = standard_param.loc[yoc][units + " unit(s)"]
        else:
            # specific demand per area
            specific_heat_demand = standard_param.loc[yoc][building_type]
        
        # get the factor to correct the gross building area to the net
        # living area
        net_floor_area_p_area = \
            sinks_standard_param.loc[sink_type]["net floor area / area"]
        demand_heat = specific_heat_demand * area * net_floor_area_p_area
        
    # if there is an area-specific heat requirement given
    else:
        demand_heat = building["heat demand"] * area
        
    demand_heat_new = demand_heat
    
    # if there is a wood stove share given by the user, reduce the
    # building heat amount by the amount which has to be produced by
    # the wood stove
    if building["wood stove share"] != "standard":
        demand_heat_new -= (float(building["wood stove share"]) * demand_heat)
    
        sheets = create_share_sink_system(
            sheets=sheets,
            standard_parameters=standard_parameters,
            sink_type=sink_type,
            label=str(building["label"]),
            share_type="wood_stove",
            annual_demand=(float(building["wood stove share"]) * demand_heat))
        
    # if there is a solar thermal share given by the user, reduce the
    # building heat amount by the amount which has to be produced by
    # the solar thermal source
    if building["solar thermal share"] != "standard":
        demand_heat_new -= (float(building["solar thermal share"]) * demand_heat)

        sheets = create_share_sink_system(
            sheets=sheets,
            standard_parameters=standard_parameters,
            sink_type=sink_type,
            label=str(building["label"]),
            share_type="st",
            annual_demand=(float(building["solar thermal share"]) * demand_heat))

    # create the building heat sink whereby it is the decision of the
    # solver which technology is producing the needed amount of heat
    sheets = create_standard_parameter_sink(
        sink_type=sink_type,
        label=str(building["label"]) + "_heat_demand",
        sink_input=str(building["label"]) + "_heat_bus",
        annual_demand=demand_heat_new,
        sheets=sheets,
        standard_parameters=standard_parameters
    )

    return sheets
    

def create_sink_ev(building: pandas.Series, sheets: dict,
                   standard_parameters: pandas.ExcelFile) -> dict:
    """
        For the modeling of electric vehicles, within this method the
        sink for electric vehicles is created.
    
        :param building: building specific data which were imported \
            from the US-Input sheet
        :type building: pandas.Series
        :param sheets: dictionary containing the pandas.Dataframes that\
                will represent the model definition's Spreadsheets
        :type sheets: dict
        :param standard_parameters: pandas imported ExcelFile \
                containing the non-building specific technology data
        :type standard_parameters: pandas.ExcelFile
        
        :return: - **sheets** (dict) - dictionary containing the \
            pandas.Dataframes that will represent the model \
            definition's Spreadsheets which was modified in this method
    """
    from program_files import create_standard_parameter_comp
    
    # multiply the electric vehicle time series with the driven
    # kilometers
    sheets["time series"].loc[:, building['label'] + "_electric_vehicle.fix"] \
        = sheets["time series"].loc[:, "electric_vehicle.fix"] \
        * building["distance of electric vehicles"]
    
    return create_standard_parameter_comp(
        specific_param={
            "label": building["label"] + "_electric_vehicle",
            "input": str(building["label"]) + "_electricity_bus",
            "nominal value": building["distance of electric vehicles"],
            "annual demand": 0
        },
        standard_parameter_info=[
            "electric vehicle electricity sink", "2_sinks", "sink type"],
        sheets=sheets,
        standard_parameters=standard_parameters)


def create_sinks(building: pandas.Series, sheets: dict,
                 standard_parameters: pandas.ExcelFile) -> dict:
    """
        In this method, the sinks necessary to represent the demand of
        a building are created one after the other. These are an
        electricity sink, a heat sink and, if provided by the user
        (distance of Electric vehicle > 0), an EV_sink. Finally they
        are appended to the return structure "sheets".
        
        :param building: building specific data which were imported \
            from the US-Input sheet
        :type building: pandas.Series
        :param sheets: dictionary containing the pandas.Dataframes that\
                will represent the model definition's Spreadsheets
        :type sheets: dict
        :param standard_parameters: pandas imported ExcelFile \
                containing the non-building specific technology data
        :type standard_parameters: pandas.ExcelFile
        
        :return: - **sheets** (dict) - dictionary containing the \
            pandas.Dataframes that will represent the model \
            definition's Spreadsheets which was modified in this method
    """
    if building["building type"]:
        area = building["gross building area"]
        # get sinks standard parameters
        sinks_standard_param = standard_parameters.parse("2_sinks")
        sinks_standard_param.set_index("sink type", inplace=True)
        
        # create electricity sink
        sheets = create_electricity_sink(
            building=building,
            area=area,
            sheets=sheets,
            sinks_standard_param=sinks_standard_param,
            standard_parameters=standard_parameters)

        # heat demand
        sheets = create_heat_sink(
            building=building,
            area=area,
            sheets=sheets,
            sinks_standard_param=sinks_standard_param,
            standard_parameters=standard_parameters)
        
        if building["distance of electric vehicles"] > 0:
            sheets = create_sink_ev(
                building=building,
                sheets=sheets,
                standard_parameters=standard_parameters)
    return sheets


def sink_clustering(building: list, sink: pandas.Series,
                    sink_parameters: list) -> list:
    """
        In this method, the current sinks of the respective cluster are
        stored in dict and the current sinks are deleted. Furthermore,
        the heat buses and heat requirements of each cluster are
        collected in order to summarize them afterwards.

        :param building: list containing the building label [0], the \
            building's parcel ID [1] and the building type [2]
        :type building: list
        :param sink: One column of the sinks sheet
        :type sink: pandas.Series
        :parameter sink_parameters: list containing clusters' sinks \
            information
        :type sink_parameters: list
        
        TODO: share sinks are currently clustered together with the \
            cluster heat demands.
        
        :return: - **sink_parameters** (list) - list containing \
            clusters' sinks information which were modified within \
            this method
    """
    # get cluster electricity sinks
    if str(building[0]) in sink["label"] and "electric" in sink["label"]:
        # get the residential electricity demands and its sinks labels
        if building[2] in ["single family building", "multi family building"]:
            sink_parameters[0] += sink["annual demand"]
            sink_parameters[8].append(sink["label"])
        # get the commercial electricity demands and its sinks labels
        elif "commercial" in building[2]:
            sink_parameters[1] += sink["annual demand"]
            sink_parameters[9].append(sink["label"])
        # get the industrial electricity demands and its sinks labels
        elif "industrial" in building[2]:
            sink_parameters[2] += sink["annual demand"]
            sink_parameters[10].append(sink["label"])
            
    # get cluster heat sinks
    elif str(building[0]) in sink["label"] and "heat" in sink["label"]:
        # append heat bus to cluster heat buses
        sink_parameters[3].append((building[2], sink["input"]))
        # get the residential heat demands
        if building[2] in ["single family building", "multi family building"]:
            sink_parameters[4] += sink["annual demand"]
        # get the commercial heat demands
        elif "commercial" in building[2]:
            sink_parameters[5] += sink["annual demand"]
        # get the industrial heat demands
        elif "industrial" in building[2]:
            sink_parameters[6] += sink["annual demand"]
        sink_parameters[7].append((building[2], sink["label"]))
    
    return sink_parameters
    

def create_cluster_electricity_sinks(standard_parameters: pandas.ExcelFile,
                                     sink_parameters: list, cluster: str,
                                     central_electricity_network: bool,
                                     sheets: dict) -> dict:
    """
        In this method, the electricity purchase price for the
        respective sink is calculated based on the electricity demand
        of the unclustered sinks. For example, if residential buildings
        account for 30% of the cluster electricity demand, 30% of the
        central electricity purchase price is formed from the
        residential tariff. In addition, the inputs of the cluster
        sinks, if there is an electricity demand, are changed to the
        cluster internal buses, so that the energy flows in the cluster
        can be correctly determined again.
        
        :param standard_parameters: pandas imported ExcelFile \
                containing the non-building specific technology data
        :type standard_parameters: pandas.ExcelFile
        :parameter sink_parameters: list containing clusters' sinks \
            information
        :type sink_parameters: list
        :param cluster: Cluster ID
        :type cluster: str
        :param central_electricity_network: boolean which decides \
            whether a central electricity exchange is possible or not
        :param sheets: dictionary containing the pandas.Dataframes that\
                will represent the model definition's Spreadsheets
        :type sheets: dict
        
        :return: - **sheets** (dict) - dictionary containing the \
            pandas.Dataframes that will represent the model \
            definition's Spreadsheets which was modified in this method
    """
    from program_files import (Link, Bus)

    total_annual_demand = sum(sink_parameters[0:3])
    # if the clusters total annual electricity demand is greater 0
    if total_annual_demand > 0:
        # if there is no cluster electricity bus
        if cluster + "_electricity_bus" not in sheets["buses"].index:
            # create the clusters electricity bus the residential
            # electricity bus is used since it is the most expensive
            # tariff of electricity import
            sheets = Bus.create_standard_parameter_bus(
                label=str(cluster) + "_electricity_bus",
                bus_type="electricity bus residential decentral",
                sheets=sheets,
                standard_parameters=standard_parameters)
            sheets["buses"].set_index("label", inplace=True, drop=False)
            label = "_electricity_bus"
            # calculate the averaged shortage costs based on the
            # percentage of the considered demand on the total demand
            sheets["buses"].loc[(str(cluster) + label), "shortage costs"] = \
                Bus.calculate_average_shortage_costs(
                    standard_parameters=standard_parameters,
                    sink_parameters=sink_parameters,
                    total_annual_demand=total_annual_demand,
                    fuel_type="electricity",
                    electricity=True
                )
        # if there is an opportunity for central electric exchange the
        # new created bus has to be connected to the central electricity
        # bus
        if central_electricity_network:
            sheets = Link.create_central_electricity_bus_connection(
                cluster=cluster,
                sheets=sheets,
                standard_parameters=standard_parameters)

    # create clustered electricity sinks
    if sink_parameters[0] > 0:
        for i in sink_parameters[8]:
            sheets["sinks"].loc[sheets["sinks"]["label"] == i, "input"] = (
                str(cluster) + "_residential_electricity_bus"
            )
    if sink_parameters[1] > 0:
        for i in sink_parameters[9]:
            sheets["sinks"].loc[sheets["sinks"]["label"] == i, "input"] = (
                str(cluster) + "_commercial_electricity_bus"
            )
    if sink_parameters[2] > 0:
        for i in sink_parameters[10]:
            sheets["sinks"].loc[sheets["sinks"]["label"] == i, "input"] = (
                str(cluster) + "_industrial_electricity_bus"
            )

    return sheets
