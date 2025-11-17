// Multi-select patch dropdown functionality

// Function to get patches from URL path
function getSelectedPatchesFromUrl() {
    const urlPath = window.location.pathname;
    const pathSegments = urlPath.split("/");
    
    // Format: /stats/patch/elo or /stats/patch/elo/specific_key
    if (pathSegments.length >= 4) {
        const patchSegment = pathSegments[2];
        // Remove 'v' prefix and split by comma
        const patches = patchSegment.replace(/^v/, '').split(',');
        return patches;
    }
    return [];
}

// Preselect checkboxes based on the URL
function preselectPatches() {
    const selectedPatches = getSelectedPatchesFromUrl();
    document.querySelectorAll('.patch-checkbox').forEach(function (checkbox) {
        if (selectedPatches.includes(checkbox.value)) {
            checkbox.checked = true;
        }
    });
}

// Initialize multi-select functionality
function initPatchMultiselect(playerurl, stats, elo, specificKey) {
    // Event listener for the "Go" button
    if (document.getElementById('redirectButton')) {
        document.getElementById('redirectButton').addEventListener('click', function () {
            // Get all the selected patches
            var selectedPatches = [];
            document.querySelectorAll('.patch-checkbox:checked').forEach(function (checkbox) {
                selectedPatches.push(checkbox.value);
            });

            // If no patches selected, prevent action
            if (selectedPatches.length === 0) {
                alert('Please select at least one patch.');
                return;
            }

            // Create a comma-delimited string of the selected patches
            var patches = 'v' + selectedPatches.join(',');

            // Construct the URL
            var url = playerurl + '/' + stats + '/' + patches + '/' + elo;
            if (specificKey && specificKey !== 'All') {
                url += '/' + specificKey;
            }

            // Redirect to the new URL
            window.location.href = url;
        });
    }

    // Prevent the dropdown from closing when clicking inside
    if (document.getElementById('patchDropdown')) {
        document.getElementById('patchDropdown').addEventListener('click', function (event) {
            event.stopPropagation();
        });

        // Add click event on checkboxes to prevent dropdown closing
        document.querySelectorAll('.patch-checkbox').forEach(function (checkbox) {
            checkbox.addEventListener('click', function (event) {
                event.stopPropagation();
            });
        });

        document.querySelectorAll('#patch-checkbox').forEach(function (label) {
            label.addEventListener('click', function (event) {
                var checkbox = this.querySelector('input[type="checkbox"]');
                if (checkbox && event.target !== checkbox) {
                    checkbox.checked = !checkbox.checked;
                }
                event.stopPropagation();
            });
        });

        // Preselect checkboxes when the page loads
        window.addEventListener('load', preselectPatches);
    }
}

