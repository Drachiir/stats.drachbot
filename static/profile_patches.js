document.addEventListener("DOMContentLoaded", function () {
    // Function to get patches from URL
    const urlParts = window.location.toString().split("?");

    function getSelectedPatchesFromUrl() {
        if (urlParts.length >= 2) {
            const urlParams = new URLSearchParams(urlParts[1]);
            if (urlParams.has('patch')) {
                const patches = urlParams.get('patch');
                if (patches.includes(",")) {
                    return patches.split(',');
                } else {
                    return [patches];
                }
            }
        }
        return [];
    }

    // Preselect checkboxes based on the URL or default patches
    function preselectPatches(defaultPatches) {
        const selectedPatches = getSelectedPatchesFromUrl();
        // If there are no patches in the URL, use the default patches
        const patchesToSelect = selectedPatches.length > 0 ? selectedPatches : defaultPatches;

        console.log("Selected patches:", patchesToSelect);
        document.querySelectorAll('.patch-checkbox').forEach(function (checkbox) {
            const checkboxValue = checkbox.value;

            // Only select the checkbox if it's an exact match (ignore catch-all patterns like v11.**)
            if (patchesToSelect.some(patch => patch === checkboxValue)) {
                checkbox.checked = true;
            }
        });
    }

    // Fetch default patches from the API and call preselectPatches
    function fetchDefaultPatches() {
        fetch('/api/defaults')
            .then(response => response.json())
            .then(data => {
                const defaultPatches = data.Defaults2 && data.Defaults2.length > 0 ? data.Defaults2[0].split(',') : [];
                preselectPatches(defaultPatches);
            })
            .catch(error => console.error('Error fetching default patches:', error));
    }

    // Event listener for the "Go" button
    document.getElementById('redirectButton').addEventListener('click', function () {
        let url;
        var selectedPatches = [];
        const checkBoxes = document.querySelectorAll('.patch-checkbox:checked');
        checkBoxes.forEach(function (checkbox) {
            selectedPatches.push(checkbox.value);
        });

        // If no patches were selected, exit early to prevent errors
        if (selectedPatches.length === 0) {
            console.error("No patches selected.");
            return; // Prevent the URL redirection
        }

        // Create a comma-delimited string of the selected patches
        var patches = selectedPatches.join(',');

        // Construct the URL without using .toString() (this was the source of the issue)
        const urlParams = new URLSearchParams(urlParts[1]);
        urlParams.set('patch', patches); // Update the 'patch' parameter

        // If there were no existing URL parameters, add the 'patch' query string
        url = urlParts[0] + "?" + urlParams.toString();

        // Redirect to the new URL
        window.location.href = url;
    });

    // Prevent the dropdown from closing when clicking inside the dropdown content
    document.getElementById('patchDropdown').addEventListener('click', function (event) {
        event.stopPropagation();  // Stop dropdown from closing when clicking inside
    });

    // Add click event directly on checkboxes to prevent issues
    document.querySelectorAll('.patch-checkbox').forEach(function (checkbox) {
        checkbox.addEventListener('click', function (event) {
            event.stopPropagation(); // Prevent dropdown from closing
        });
    });
    document.querySelectorAll('#patch-checkbox').forEach(function (label) {
        label.addEventListener('click', function (event) {
            var checkbox = this.querySelector('input[type="checkbox"]');
            checkbox.checked = !checkbox.checked; // Toggle checkbox state
            event.stopPropagation(); // Prevent dropdown from closing
        });
    });

    // Preselect checkboxes when the page loads
    window.onload = function() {
        fetchDefaultPatches();
    };
});