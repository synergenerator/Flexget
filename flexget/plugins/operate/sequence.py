import logging
from flexget.plugin import register_plugin, get_plugin_by_name, get_plugin_keywords, get_phases_by_plugin, phase_methods

log = logging.getLogger('sequence')


class PluginSequence(object):
    """ Allows the same plugin to be configured multiple times in a feed.

    Example:
    sequence:
      - rss: http://feeda.com
      - rss: http://feedb.com
    """

    def validator(self):
        from flexget import validator
        root = validator.factory()
        valid_plugins = root.accept('list').accept('dict')
        for plugin_name in get_plugin_keywords():
            plugin = get_plugin_by_name(plugin_name)
            if plugin.api_ver > 1 and hasattr(plugin.instance, 'validator'):
                valid_plugins.accept(plugin.instance.validator, key=plugin_name)
        return root

    def __getattr__(self, item):
        """Returns a function for all on_feed_* and on_process_* events, that runs all the configured plugins."""
        for phase, method in phase_methods.iteritems():
            # TODO: Deal with entry phases
            if item == method and phase not in ['accept', 'reject', 'fail']:
                break
        else:
            raise AttributeError(item)

        def handle_phase(feed, config):
            """Function that runs all of the configured plugins which act on the current phase."""
            # Keep a list of all results, for input plugin combining
            results = []
            for item in config:
                for plugin_name, plugin_config in item.iteritems():
                    if phase in get_phases_by_plugin(plugin_name):
                        method = get_plugin_by_name(plugin_name).phase_handlers[phase]
                        log.debug('Running plugin %s' % plugin_name)
                        result = method(feed, plugin_config)
                        if isinstance(result, list):
                            results.extend(result)
            return results

        return handle_phase


register_plugin(PluginSequence, 'sequence', api_ver=2, debug=True)
