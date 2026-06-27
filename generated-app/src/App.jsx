} catch (fetchError) {
  setError(
    `${fetchError.message || "Something went wrong loading trivia."} Retried ${TRIVIA_FETCH_RETRY_COUNT} times, then switched to fallback questions.`
  );
  const fallbackRounds = buildFallbackRounds(nextSubject);
  ...
}
