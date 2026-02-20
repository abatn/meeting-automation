import React from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { TextField, Button, Box } from '@mui/material';
import { DateTimePicker } from '@mui/x-date-pickers/DateTimePicker';
import { useTranslation } from 'react-i18next';

const meetingSchema = z.object({
  title: z.string().min(1),
  dateTime: z.date(),
});

type MeetingFormInputs = z.infer<typeof meetingSchema>;

const MeetingPlanner: React.FC = () => {
  const { t } = useTranslation();
  const { register, handleSubmit, setValue, formState: { errors } } = useForm<MeetingFormInputs>({
    resolver: zodResolver(meetingSchema),
  });

  const onSubmit = (data: MeetingFormInputs) => {
    // TODO: Handle meeting creation
    console.log(data);
  };

  return (
    <Box component="form" onSubmit={handleSubmit(onSubmit)} noValidate>
      <TextField
        margin="normal"
        required
        fullWidth
        id="title"
        label={t('meetingTitle')}
        autoFocus
        {...register('title')}
        error={!!errors.title}
        helperText={errors.title?.message}
      />
      <DateTimePicker
        label={t('meetingDateTime')}
        onChange={(date) => setValue('dateTime', date as Date)}
        slotProps={{ textField: { margin: 'normal', fullWidth: true } }}
      />
      <Button
        type="submit"
        fullWidth
        variant="contained"
        sx={{ mt: 3, mb: 2 }}
      >
        {t('planMeeting')}
      </Button>
    </Box>
  );
};

export default MeetingPlanner;