document.addEventListener('DOMContentLoaded', function () {
    const profileTypeField = document.getElementById('id_profile_type');
    const designationField = document.getElementById('id_designation');

    if (!profileTypeField || !designationField) {
        return;
    }

    const designationMap = {
        FOUNDER: 'প্রতিষ্ঠাতা',
        HEADMASTER: 'প্রধান শিক্ষক',
        PRESIDENT: 'সভাপতি',
        COMMITTEE: 'ম্যানেজিং কমিটি',
    };

    let lastAutoDesignation = '';

    function applyDesignation() {
        const defaultDesignation = designationMap[profileTypeField.value] || '';
        const currentValue = designationField.value.trim();

        if (!currentValue || currentValue === lastAutoDesignation) {
            designationField.value = defaultDesignation;
            lastAutoDesignation = defaultDesignation;
        }
    }

    profileTypeField.addEventListener('change', applyDesignation);
    applyDesignation();
});
