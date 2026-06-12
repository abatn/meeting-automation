export const animations = `
  @keyframes pulse-opacity {
    0%   { opacity: 1; transform: scale(1); }
    50%  { opacity: 0.5; transform: scale(1.1); }
    100% { opacity: 1; transform: scale(1); }
  }
  @keyframes pulse-ripple {
    0% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.4); }
    70% { box-shadow: 0 0 0 10px rgba(16, 185, 129, 0); }
    100% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
  }
  @keyframes wave {
    0%, 100% { transform: scaleY(0.4); }
    50%       { transform: scaleY(1.2); }
  }
`;
