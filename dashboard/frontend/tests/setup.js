// Vitest setup file
// Add global test utilities and mocks here

// Mock console methods in tests to reduce noise
global.console = {
  ...console,
  error: jest.fn(),
  warn: jest.fn(),
}
