document.addEventListener("DOMContentLoaded", function () {
    // Function to get patches from URL
    const urlParts = window.location.toString().split("=")

    function getSelectedPatchesFromUrl() {
        if (urlParts.length >= 1) {
            if (urlParts[1].includes(",")) {
                return urlParts[1].split(',');
            } else {
                return [urlParts[1]]
            }
        }
        return [];
    }

    // Preselect checkboxes based on the URL
    function preselectPatches() {
        const selectedPatches = getSelectedPatchesFromUrl();
        console.log(selectedPatches)
        document.querySelectorAll('.patch-checkbox').forEach(function (checkbox) {
            if (selectedPatches.includes(checkbox.value)) {
                checkbox.checked = true;
            }
        });

        // If all checkboxes are checked, check the "Select All" box
        const allChecked = selectedPatches.length > 0 && selectedPatches.length === document.querySelectorAll('.patch-checkbox').length;
        document.getElementById('selectAll').checked = allChecked;
    }

    // Event listener for the "Select/Unselect All" checkbox
    document.getElementById('selectAll').addEventListener('change', function () {
        var isChecked = this.checked;
        document.querySelectorAll('.patch-checkbox').forEach(function (checkbox) {
            checkbox.checked = isChecked;
        });
    });

    // Event listener for the "Go" button
    document.getElementById('redirectButton').addEventListener('click', function () {
        let url;
        var selectedPatches = [];
        const checkBoxes = document.querySelectorAll('.patch-checkbox:checked')
        checkBoxes.forEach(function (checkbox) {
            selectedPatches.push(checkbox.value);
        });
        // Create a comma-delimited string of the selected patches
        var patches = selectedPatches.join(',');

        // Construct the URL
        if (urlParts[0].includes("?patch")){
            url = urlParts[0] + "=" + patches;
        } else {
            url = urlParts[0] + "?patch=" + patches;
        }
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
    window.onload = preselectPatches;
});