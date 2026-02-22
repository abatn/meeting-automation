import React from 'react';
import { render, screen } from '@testing-library/react';
import { Provider } from 'react-redux';
import { store } from '../../store';
import ActionTracker from '../../components/actions/ActionTracker';

describe('ActionTracker', () => {
  test('renders action items list', () => {
    render(
      <Provider store={store}>
        <ActionTracker />
      </Provider>
    );
    expect(screen.getByText(/Actions/i)).toBeInTheDocument();
  });
});
