import { textGenBackend } from './gpt';

/**
 * Use PaLM API to generate text based on a given prompt
 * @param apiKey PaLM API key
 * @param requestID Worker request ID
 * @param prompt Prompt to give to the PaLM model
 * @param temperature Model temperature
 * @param stopSequences Strings to stop the generation
 * @param detail Extra string information to include (will be returned)
 */
export const textGenPalm = async (
  apiKey: string,
  requestID: string,
  prompt: string,
  temperature: number,
  useCache: boolean = true,
  stopSequences: string[] = [],
  detail: string = ''
) => {
  return textGenBackend(
    'palm',
    apiKey,
    requestID,
    prompt,
    temperature,
    'text-bison-001',
    useCache,
    stopSequences,
    detail,
    '[palm]'
  );
};
