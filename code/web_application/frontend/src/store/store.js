import { configureStore } from "@reduxjs/toolkit";
import recallsReducer from "./recallsSlice";

export const store = configureStore({
  reducer: {
    recalls: recallsReducer,
  },
});
