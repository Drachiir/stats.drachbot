document.addEventListener("DOMContentLoaded", function () {
    // Function to get patches from URL path
    function getSelectedPatchesFromUrl() {
        const urlPath = window.location.pathname;
        const pathSegments = urlPath.split("/");

        if (pathSegments.length === 7) {
            const patchSegment = pathSegments[pathSegments.length - 3];
            return patchSegment.includes(",") ? patchSegment.split(",") : [patchSegment];
        }
        if (pathSegments.length === 8) {
            const patchSegment = pathSegments[pathSegments.length - 4];
            return patchSegment.includes(",") ? patchSegment.split(",") : [patchSegment];
        }
        return [];
    }

    // Preselect checkboxes based on the URL or default patches
    function preselectPatches(defaultPatches) {
        const selectedPatches = getSelectedPatchesFromUrl();
        const patchesToSelect = selectedPatches.length > 0 ? selectedPatches : defaultPatches;

        console.log("Selected patches:", patchesToSelect);
        document.querySelectorAll('.patch-checkbox').forEach(function (checkbox) {
            const checkboxValue = checkbox.value;

            // Only select the checkbox if it's an exact match
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
        const selectedPatches = [];
        const checkBoxes = document.querySelectorAll('.patch-checkbox:checked');
        checkBoxes.forEach(function (checkbox) {
            selectedPatches.push(checkbox.value);
        });

        // Exit early if no patches were selected
        if (selectedPatches.length === 0) {
            console.error("No patches selected.");
            return;
        }

        // Create a comma-delimited string of the selected patches
        const patches = selectedPatches.join(',');

        // Construct the new URL
        const urlPath = window.location.pathname.split("/");
        console.log(urlPath[urlPath.length - 4])
        if (urlPath.length === 7) {
            urlPath[urlPath.length - 3] = patches; // Replace the patch segment
        }
        if (urlPath.length === 8) {
            urlPath[urlPath.length - 4] = patches; // Replace the patch segment
        }
        // Redirect to the new URL
        window.location.href = window.location.origin + urlPath.join("/");
    });

    // Prevent the dropdown from closing when clicking inside the dropdown content
    document.getElementById('patchDropdown').addEventListener('click', function (event) {
        event.stopPropagation(); // Stop dropdown from closing
    });

    // Add click event directly on checkboxes to prevent issues
    document.querySelectorAll('.patch-checkbox').forEach(function (checkbox) {
        checkbox.addEventListener('click', function (event) {
            event.stopPropagation(); // Prevent dropdown from closing
        });
    });

    document.querySelectorAll('#patch-checkbox').forEach(function (label) {
        label.addEventListener('click', function (event) {
            const checkbox = this.querySelector('input[type="checkbox"]');
            checkbox.checked = !checkbox.checked; // Toggle checkbox state
            event.stopPropagation(); // Prevent dropdown from closing
        });
    });

    // Preselect checkboxes when the page loads
    window.onload = function () {
        fetchDefaultPatches();
    };
});