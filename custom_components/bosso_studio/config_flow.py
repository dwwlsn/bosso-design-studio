import probatio as vol
from homeassistant import config_entries


class StudioConfigFlow(config_entries.ConfigFlow, domain="bosso_studio"):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        if user_input is not None:
            return self.async_create_entry(title="Bosso Design Studio", data=user_input)
        return self.async_show_form(step_id="user", data_schema=vol.Schema({
            vol.Optional("enable_playback", default=False): bool
        }))

