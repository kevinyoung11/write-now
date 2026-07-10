import { textGenBackend } from './gpt';

/**
 * Use Gemini API to generate text based on a given prompt
 * @param apiKey Gemini API key
 * @param requestID Worker request ID
 * @param prompt Prompt to give to the Gemini model
 * @param temperature Model temperature
 * @param useCache Whether to use local cache
 * @param stopSequences Strings to stop the generation
 * @param detail Extra string information to include (will be returned)
 */
export const textGenGemini = async (
  apiKey: string,
  requestID: string,
  prompt: string,
  temperature: number,
  useCache: boolean = false,
  stopSequences: string[] = [],
  detail: string = ''
) => {
  return textGenBackend(
    'gemini',
    apiKey,
    requestID,
    prompt,
    temperature,
    'gemini-pro',
    useCache,
    stopSequences,
    detail,
    '[gemini]'
  );
};
