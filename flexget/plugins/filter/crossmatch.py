import logging
from flexget.plugin import register_plugin, add_plugin_validators, PluginError, get_plugin_by_name

log = logging.getLogger('crossmatch')


class CrossMatch(object):
    """
    Perform action based on item on current feed and other inputs.

    Example::

      crossmatch:
        from:
          - rss: http://example.com/
        fields:
          - title
        action: reject
    """

    def validator(self):
        from flexget.validator import factory
        root = factory('dict')
        root.accept('list', key='fields', required=True).accept('text')
        root.accept('choice', key='action', required=True).accept_choices(['accept', 'reject'])

        inputs = root.accept('list', key='from', required=True)
        add_plugin_validators(inputs, phase='input')
        return root

    def on_feed_filter(self, feed, config):

        fields = config['fields']
        action = config['action']

        result = []

        # TODO: xxx
        # we probably want to have common "run and combine inputs" function sometime soon .. this code is in
        # few places already (discover, inputs, ...)
        # code written so that this can be done easily ...
        for item in config['from']:
            for input_name, input_config in item.iteritems():
                input = get_plugin_by_name(input_name)
                if input.api_ver == 1:
                    raise PluginError('Plugin %s does not support API v2' % input_name)
                method = input.phase_handlers['input']
                try:
                    result.extend(method(feed, input_config))
                except PluginError, e:
                    log.warning('Error during input plugin %s: %s' % (input_name, e))
                    continue
                if not result:
                    log.warning('Input %s did not return anything' % input_name)
                    continue

        # perform action on intersecting entries
        for entry in feed.entries:
            for generated_entry in result:
                log.trace('checking if %s matches %s' % (entry['title'], generated_entry['title']))
                common = self.entry_intersects(entry, generated_entry, fields)
                if common:
                    msg = 'intersects with %s on field(s) %s' % \
                          (generated_entry['title'], ', '.join(common))
                    if action == 'reject':
                        feed.reject(entry, msg)
                    if action == 'accept':
                        feed.accept(entry, msg)

    def entry_intersects(self, e1, e2, fields=None):
        """
        :param e1: First :class:`flexget.entry.Entry`
        :param e2: Second :class:`flexget.entry.Entry`
        :param fields: List of fields which are checked
        :return: List of field names in common
        """

        if fields is None:
            fields = []

        common_fields = []

        for field in fields:
            # TODO: simplify if seems to work (useless debug)
            log.trace('checking field %s' % field)
            v1 = e1.get(field, object())
            v2 = e2.get(field, object())
            log.trace('v1: %r' % v1)
            log.trace('v2: %r' % v2)

            if v1 == v2:
                common_fields.append(field)
            else:
                log.trace('not matching')
        return common_fields


register_plugin(CrossMatch, 'crossmatch', api_ver=2)
