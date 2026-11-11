(function () {
    function setupSubjectForm() {
        const classSelect = document.getElementById('id_class_level');
        const groupSelect = document.getElementById('id_group_name');
        const middleField = document.getElementById('id_middle_routine_subject');
        const seniorField = document.getElementById('id_senior_routine_subject');

        if (!classSelect || !groupSelect || !middleField || !seniorField) {
            return;
        }

        function updateFields() {
            const classLevel = classSelect.value;
            const isMiddleClass = ['6', '7', '8'].includes(classLevel);
            const isSeniorClass = ['9', '10'].includes(classLevel);
            const isEditing = document.body.classList.contains('change-form');
            const allGroups = groupSelect.querySelector('option[value="ALL"]');

            middleField.closest('.form-row').hidden = isEditing || !isMiddleClass;
            seniorField.closest('.form-row').hidden = isEditing || !isSeniorClass;
            if (allGroups) {
                allGroups.hidden = !isSeniorClass;
                if (!isSeniorClass && groupSelect.value === 'ALL') {
                    groupSelect.value = '';
                }
            }
        }

        classSelect.addEventListener('change', updateFields);
        updateFields();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', setupSubjectForm);
    } else {
        setupSubjectForm();
    }
})();
