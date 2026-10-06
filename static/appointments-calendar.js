    const calendarGridConfig = JSON.parse(document.getElementById('calendar-grid-config')?.textContent || '{"startHour":7,"endHour":20,"hourHeight":72,"defaultDurationMinutes":50}');
    let draggedAppointment = null;

    function timeFromPointer(event, target) {
      const rect = target.getBoundingClientRect();
      const headerHeight = target.querySelector('.gcal-day-head')?.getBoundingClientRect().height || 64;
      const y = Math.max(0, event.clientY - rect.top - headerHeight);
      const rawMinutes = Math.round((y / calendarGridConfig.hourHeight) * 60);
      const roundedMinutes = Math.max(0, Math.round(rawMinutes / 15) * 15);
      const totalMinutes = calendarGridConfig.startHour * 60 + roundedMinutes;
      const hours = Math.min(calendarGridConfig.endHour, Math.floor(totalMinutes / 60));
      const minutes = hours === calendarGridConfig.endHour ? 0 : totalMinutes % 60;
      return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}`;
    }

    function datetimeFor(dateValue, timeValue, durationMinutes = calendarGridConfig.defaultDurationMinutes) {
      const [hours, minutes] = timeValue.split(':').map(Number);
      const start = new Date(`${dateValue}T00:00:00`);
      start.setHours(hours, minutes, 0, 0);
      const end = new Date(start.getTime() + durationMinutes * 60000);
      const format = (value) => `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, '0')}-${String(value.getDate()).padStart(2, '0')}T${String(value.getHours()).padStart(2, '0')}:${String(value.getMinutes()).padStart(2, '0')}`;
      return { start: format(start), end: format(end) };
    }

    function minutesFor(timeValue) {
      const [hours, minutes] = timeValue.split(':').map(Number);
      return hours * 60 + minutes;
    }

    function isAvailable(column, timeValue, durationMinutes = calendarGridConfig.defaultDurationMinutes) {
      if (column.dataset.availabilityConfigured !== '1') return true;
      const start = minutesFor(timeValue);
      const end = start + durationMinutes;
      return (column.dataset.availabilityRanges || '').split(';').filter(Boolean).some((range) => {
        const [rangeStart, rangeEnd] = range.split('-').map(Number);
        return rangeStart <= start && rangeEnd >= end;
      });
    }

    document.querySelector('[data-availability-review]')?.addEventListener('click', (event) => {
      event.preventDefault();
      const panel = document.getElementById('availability-changes');
      panel.open = true;
      panel.querySelector('summary').focus();
      panel.scrollIntoView({ block: 'start' });
    });

    document.addEventListener('dragstart', (event) => {
      const item = event.target.closest('[data-draggable-appointment]');
      if (!item) return;
      draggedAppointment = {
        title: item.dataset.appointmentTitle,
        time: item.dataset.appointmentTime,
        duration: Number(item.dataset.appointmentDuration) || calendarGridConfig.defaultDurationMinutes,
        url: item.dataset.rescheduleUrl,
        trigger: item,
      };
      event.dataTransfer.effectAllowed = 'move';
      event.dataTransfer.setData('text/plain', draggedAppointment.title || 'Appointment');
    });

    document.addEventListener('dragover', (event) => {
      const target = event.target.closest('[data-drop-date]');
      if (!target || !draggedAppointment) return;
      event.preventDefault();
      target.classList.add('drop-ready');
    });

    document.addEventListener('dragleave', (event) => {
      const target = event.target.closest('[data-drop-date]');
      if (target) target.classList.remove('drop-ready');
    });

    document.addEventListener('drop', (event) => {
      const target = event.target.closest('[data-drop-date]');
      if (!target || !draggedAppointment) return;
      event.preventDefault();
      target.classList.remove('drop-ready');
      const dialog = document.getElementById('reschedule-modal');
      const form = dialog?.querySelector('[data-reschedule-form]');
      if (!dialog || !form) return;
      const newTime = target.classList.contains('gcal-day-column') ? timeFromPointer(event, target) : draggedAppointment.time || '09:00';
      const feedback = dialog.querySelector('[data-scheduling-feedback]');
      if (feedback) feedback.hidden = !target.classList.contains('gcal-day-column') || isAvailable(target, newTime, draggedAppointment.duration);
      form.action = draggedAppointment.url;
      form.elements.date.value = target.dataset.dropDate;
      form.elements.time.value = newTime;
      form.elements.next.value = `${window.location.pathname}${window.location.search}`;
      dialog.querySelector('[data-reschedule-title]').textContent = `Move ${draggedAppointment.title || 'appointment'}`;
      dialog._returnFocus = draggedAppointment.trigger;
      dialog.showModal();
      form.elements.date.focus();
      draggedAppointment = null;
    });

    document.addEventListener('click', (event) => {
      const column = event.target.closest('.gcal-day-column[data-drop-date]');
      if (!column || event.target.closest('a, button, input, select, textarea')) return;
      const dialog = document.getElementById('appointment-create-modal');
      if (!dialog || typeof dialog.showModal !== 'function') return;
      const selectedTime = timeFromPointer(event, column);
      const values = datetimeFor(column.dataset.dropDate, selectedTime);
      const feedback = dialog.querySelector('[data-scheduling-feedback]');
      if (feedback) feedback.hidden = isAvailable(column, selectedTime);
      dialog.querySelector('[name="starts_at"]').value = values.start;
      dialog.querySelector('[name="ends_at"]').value = values.end;
      dialog._returnFocus = column.querySelector('[data-modal-target="appointment-create-modal"]');
      dialog.showModal();
      dialog.querySelector('[name="client"]')?.focus();
    });

    document.addEventListener('click', (event) => {
      const trigger = event.target.closest('[data-modal-target]');
      if (!trigger) return;
      const dialog = document.getElementById(trigger.dataset.modalTarget);
      if (!dialog || typeof dialog.showModal !== 'function') return;
      event.preventDefault();
      const feedback = dialog.querySelector('[data-scheduling-feedback]');
      if (feedback) feedback.hidden = true;
      if (trigger.dataset.appointmentDate) {
        const start = dialog.querySelector('[name="starts_at"]');
        const end = dialog.querySelector('[name="ends_at"]');
        start.value = `${trigger.dataset.appointmentDate}T09:00`;
        end.value = `${trigger.dataset.appointmentDate}T09:50`;
      }
      if (trigger.dataset.availabilityDate) {
        dialog.querySelector('[name="date"]').value = trigger.dataset.availabilityDate;
        dialog.querySelector('[name="starts_at"]').value = '09:00';
        dialog.querySelector('[name="ends_at"]').value = '17:00';
        dialog.querySelector('[name="end_date"]').value = '';
        dialog.querySelector('[name="is_available"]').checked = true;
        dialog.querySelector('[data-availability-prompt]').hidden = true;
      }
    }, true);
    document.addEventListener('click', (event) => {
      const trigger = event.target.closest('[data-modal-close]');
      if (trigger) trigger.closest('dialog')?.close();
    });

    document.addEventListener('click', (event) => {
      const trigger = event.target.closest('button[data-reschedule-url]');
      if (!trigger) return;
      const dialog = document.getElementById('reschedule-modal');
      const form = dialog?.querySelector('[data-reschedule-form]');
      if (!form) return;
      const sessionDialog = trigger.closest('dialog');
      sessionDialog?.close();
      const feedback = dialog.querySelector('[data-scheduling-feedback]');
      if (feedback) feedback.hidden = true;
      form.action = trigger.dataset.rescheduleUrl;
      form.elements.date.value = trigger.dataset.rescheduleDate;
      form.elements.time.value = trigger.dataset.rescheduleTime;
      form.elements.next.value = window.location.pathname + window.location.search;
      dialog.querySelector('[data-reschedule-title]').textContent = `Move ${trigger.dataset.rescheduleTitle || 'appointment'}`;
      dialog._returnFocus = document.querySelector(`[data-modal-target="appointment-modal-${sessionDialog?.id.replace('appointment-modal-', '')}"]`) || trigger;
      dialog.showModal();
      form.elements.date.focus();
    });

    document.querySelectorAll('form.appointment-form').forEach((form) => {
      const start = form.querySelector('[name="starts_at"]');
      const end = form.querySelector('[name="ends_at"]');
      if (!start || !end) return;
      const duration = () => (new Date(end.value) - new Date(start.value)) / 60000;
      let minutes = duration() > 0 ? duration() : calendarGridConfig.defaultDurationMinutes;
      start.addEventListener('focus', () => { if (duration() > 0) minutes = duration(); });
      end.addEventListener('change', () => { if (duration() > 0) minutes = duration(); });
      start.addEventListener('change', () => {
        if (!start.value) return;
        const values = datetimeFor(start.value.slice(0, 10), start.value.slice(11), minutes);
        end.value = values.end;
      });
    });

    document.querySelector('[data-edit-reschedule]')?.addEventListener('click', () => {
      const start = document.querySelector('#appointment-form [name="starts_at"]');
      start?.focus();
      start?.scrollIntoView({ block: 'center', behavior: 'smooth' });
    });
