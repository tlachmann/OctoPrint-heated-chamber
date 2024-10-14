/*
 * View model for OctoPrint-Heatedchamber
 *
 * Author: Filippo De Luca
 * License: AGPLv3
 */
$(function() {
    function HeatedChamberViewModel(parameters) {
        var self = this;
        self.settingsViewModel = parameters[0];
    }

    /* view model class, parameters for constructor, container to bind to
     * Please see http://docs.octoprint.org/en/master/plugins/viewmodels.html#registering-custom-viewmodels for more details
     * and a full list of the available options.
     */
    OCTOPRINT_VIEWMODELS.push({
        construct: HeatedChamberViewModel,
        dependencies: ["settingsViewModel"],
        elements: ["#settings_plugin_HeatedChamber"]
    });
});
