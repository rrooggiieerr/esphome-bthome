"""
 BTHome protocol virtual sensors for ESPHome

 Author: Attila Farago
 """

from esphome.cpp_generator import RawExpression
import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.config_validation import hex_int_range, has_at_least_one_key
from esphome import automation
from esphome.components import binary_sensor, sensor
from esphome.const import (
    CONF_ID,
    CONF_NAME,
    CONF_MAC_ADDRESS,
)
from esphome.core import CORE, coroutine_with_priority
from esphome.components.bthome_receiver_base.const import (
    MEASUREMENT_TYPES_SENSOR,
    MEASUREMENT_TYPES_BINARY_SENSOR,
)

CONF_BTHomeReceiverBaseHub_ID = "BTHomeReceiverBaseHub_ID"
CONF_NAME_PREFIX = "name_prefix"
CONF_DUMP_OPTION = "dump"
CONF_SENSORS = "sensors"
CONF_MEASUREMENT_TYPE = "measurement_type"

CODEOWNERS = ["@afarago"]
DEPENDENCIES = []
AUTO_LOAD = [
    "bthome_base",
    "binary_sensor",
    "sensor",
]

bthome_receiver_base_ns = cg.esphome_ns.namespace("bthome_receiver_base")

DumpOption = bthome_receiver_base_ns.enum("DumpOption")
DUMP_OPTION = {
    "NONE": DumpOption.DumpOption_None,
    "UNMATCHED": DumpOption.DumpOption_Unmatched,
    "ALL": DumpOption.DumpOption_All,
}


class Generator:
    hub_ = {}

    def hub_factory(self):
        return bthome_receiver_base_ns.class_("BTHomeReceiverBaseHub", cg.Component)

    def get_hub(self):
        if not self.hub_:
            self.hub_ = self.hub_factory()
        return self.hub_

    def generate_component_config(self):
        CONFIG_SCHEMA = self.generate_component_schema()
        to_code = self.generate_to_code()

        return CONFIG_SCHEMA, to_code

    def generate_component_schema(self):
        CONFIG_SCHEMA = cv.Schema(
            {
                cv.GenerateID(): cv.declare_id(self.get_hub()),
                cv.Optional(CONF_DUMP_OPTION): cv.enum(
                    DUMP_OPTION, upper=True, space="_"
                ),
            }
        ).extend(cv.COMPONENT_SCHEMA)
        return CONFIG_SCHEMA

    async def generate_to_code_body(self, config):
        var = cg.new_Pvariable(config[CONF_ID])
        await cg.register_component(var, config)

        if CONF_DUMP_OPTION in config:
            cg.add(var.set_dump_option(config[CONF_DUMP_OPTION]))
        
        return var

    def generate_to_code(self):
        async def to_code(config):
            await self.generate_to_code_body(config)
        return to_code

    def generate_sensor_configs(self, is_binary_sensor):
        sensor_base = binary_sensor.BinarySensor if is_binary_sensor else sensor.Sensor
        MEASUREMENT_TYPES = (
            MEASUREMENT_TYPES_BINARY_SENSOR
            if is_binary_sensor
            else MEASUREMENT_TYPES_SENSOR
        )
        schema_base = (
            binary_sensor.BINARY_SENSOR_SCHEMA
            if is_binary_sensor
            else sensor.SENSOR_SCHEMA
        )
        register_async_fn = (
            binary_sensor.register_binary_sensor
            if is_binary_sensor
            else sensor.register_sensor
        )
        cpp_classname = (
            "BTHomeReceiverBaseBinarySensor"
            if is_binary_sensor
            else "BTHomeReceiverBaseSensor"
        )

        BTHomeReceiverBaseDevice = bthome_receiver_base_ns.class_(
            "BTHomeReceiverBaseDevice", cg.Component
        )

        def _check_measurement_type(value):
            if isinstance(value, int):
                return value
            try:
                return int(value)
            except ValueError:
                pass

            if not value in MEASUREMENT_TYPES:
                raise cv.Invalid(f"Invalid measurement type '{value}'!")

            return MEASUREMENT_TYPES[value]

        def validate_measurement_type(value):
            value = _check_measurement_type(value)
            return value

        ReceiverSensor = bthome_receiver_base_ns.class_(
            cpp_classname, sensor_base, cg.Component
        )

        CONFIG_SCHEMA = cv.All(
            cv.Schema(
                {
                    cv.GenerateID(CONF_BTHomeReceiverBaseHub_ID): cv.use_id(
                        self.get_hub()
                    ),
                    cv.GenerateID(): cv.declare_id(BTHomeReceiverBaseDevice),
                    cv.Required(CONF_MAC_ADDRESS): cv.mac_address,
                    cv.Optional(CONF_NAME_PREFIX): cv.string,
                    cv.Optional(CONF_DUMP_OPTION): cv.enum(
                        DUMP_OPTION, upper=True, space="_"
                    ),
                    cv.Required(CONF_SENSORS): cv.All(
                        cv.ensure_list(
                            schema_base.extend(
                                {
                                    cv.GenerateID(): cv.declare_id(ReceiverSensor),
                                    cv.Required(
                                        CONF_MEASUREMENT_TYPE
                                    ): validate_measurement_type,
                                }
                            ).extend(cv.COMPONENT_SCHEMA)
                        ),
                        cv.Length(min=1),
                    ),
                }
            ).extend(cv.COMPONENT_SCHEMA)
        )

        async def to_code(config):
            paren = await cg.get_variable(config[CONF_BTHomeReceiverBaseHub_ID])
            var = cg.new_Pvariable(config[CONF_ID])
            await cg.register_component(var, config)

            cg.add(var.set_address(config[CONF_MAC_ADDRESS].as_hex))
            cg.add(paren.register_device(var))

            if CONF_DUMP_OPTION in config:
                cg.add(var.set_dump_option(config[CONF_DUMP_OPTION]))

            # iterate around the subsensors
            for i, config_item in enumerate(config[CONF_SENSORS]):
                var_item = cg.new_Pvariable(config_item[CONF_ID])
                if CONF_NAME_PREFIX in config:
                    config_item[CONF_NAME] = (
                        config[CONF_NAME_PREFIX] + " " + config_item[CONF_NAME]
                    )

                await cg.register_component(var_item, config_item)
                await register_async_fn(var_item, config_item)
                cg.add(
                    paren.register_sensor(
                        var, config[CONF_MAC_ADDRESS].as_hex, var_item
                    )
                )

                if isinstance(config_item[CONF_MEASUREMENT_TYPE], dict):
                    measurement_type_record = config_item[CONF_MEASUREMENT_TYPE]

                    cg.add(
                        var_item.set_measurement_type(
                            measurement_type_record["measurement_type"]
                        )
                    )
                    if (
                        measurement_type_record.get("accuracy_decimals")
                        and not "accuracy_decimals" in config
                    ):
                        cg.add(
                            var_item.set_accuracy_decimals(
                                measurement_type_record["accuracy_decimals"]
                            )
                        )
                    if (
                        measurement_type_record.get("unit_of_measurement")
                        and not "unit_of_measurement" in config
                    ):
                        cg.add(
                            var_item.set_unit_of_measurement(
                                measurement_type_record["unit_of_measurement"]
                            )
                        )
                    if (
                        measurement_type_record.get("device_class")
                        and not "device_class" in config
                    ):
                        cg.add(
                            var_item.set_device_class(
                                measurement_type_record["device_class"]
                            )
                        )
                else:
                    cg.add(
                        var_item.set_measurement_type(
                            config_item[CONF_MEASUREMENT_TYPE]
                        )
                    )

        return CONFIG_SCHEMA, to_code