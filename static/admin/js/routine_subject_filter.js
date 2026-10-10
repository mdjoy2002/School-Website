(function () {
    function setupRoutineSubjectFilter() {
        const classSelect = document.getElementById('id_class_name');
        const groupSelect = document.getElementById('id_group_name');
        const subjectSelect = document.getElementById('id_subject_option');
        const codeInput = document.getElementById('id_subject_code_display');

        if (!classSelect || !groupSelect || !subjectSelect || !codeInput) {
            return;
        }

        function updateSubjects() {
            const className = classSelect.value;
            const groupName = groupSelect.value;

            Array.from(subjectSelect.options).forEach(function (option) {
                if (!option.value) {
                    return;
                }

                const sameClass = option.dataset.classLevel === className;
                const subjectGroup = option.dataset.groupName || '';
                const sameGroup = !subjectGroup ||
                    ((className === '9' || className === '10') && subjectGroup === groupName);
                option.hidden = !(sameClass && sameGroup);
            });

            const selectedOption = subjectSelect.selectedOptions[0];
            if (selectedOption && selectedOption.value && selectedOption.hidden) {
                subjectSelect.value = '';
            }
            const selectedCodeOption = subjectSelect.selectedOptions[0];
            codeInput.value = selectedCodeOption ? selectedCodeOption.dataset.code || '' : '';
        }

        classSelect.addEventListener('change', updateSubjects);
        groupSelect.addEventListener('change', updateSubjects);
        subjectSelect.addEventListener('change', updateSubjects);
        updateSubjects();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', setupRoutineSubjectFilter);
    } else {
        setupRoutineSubjectFilter();
    }
})();
