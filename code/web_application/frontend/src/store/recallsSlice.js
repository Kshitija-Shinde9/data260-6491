import { createAsyncThunk, createSlice } from "@reduxjs/toolkit";
import axios from "axios";

const api = axios.create({
  baseURL: "/api",
  withCredentials: true,
  headers: { "Content-Type": "application/json" },
});

function errorMessage(err) {
  const detail = err.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map((d) => d.msg || JSON.stringify(d)).join("; ");
  }
  return err.message || "Request failed";
}

export const fetchRecalls = createAsyncThunk(
  "recalls/fetchAll",
  async (_, { rejectWithValue }) => {
    try {
      const { data } = await api.get("/recalls");
      return data;
    } catch (err) {
      return rejectWithValue(errorMessage(err));
    }
  }
);

export const createRecall = createAsyncThunk(
  "recalls/create",
  async (payload, { rejectWithValue }) => {
    try {
      const { data } = await api.post("/recalls", payload);
      return data;
    } catch (err) {
      return rejectWithValue(errorMessage(err));
    }
  }
);

export const updateRecall = createAsyncThunk(
  "recalls/update",
  async ({ id, payload }, { rejectWithValue }) => {
    try {
      const { data } = await api.put(`/recalls/${id}`, payload);
      return data;
    } catch (err) {
      return rejectWithValue(errorMessage(err));
    }
  }
);

export const deleteRecall = createAsyncThunk(
  "recalls/delete",
  async (id, { rejectWithValue }) => {
    try {
      await api.delete(`/recalls/${id}`);
      return id;
    } catch (err) {
      return rejectWithValue(errorMessage(err));
    }
  }
);

const recallsSlice = createSlice({
  name: "recalls",
  initialState: {
    items: [],
    status: "idle",
    error: null,
  },
  reducers: {
    clearRecallError(state) {
      state.error = null;
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchRecalls.pending, (state) => {
        state.status = "loading";
        state.error = null;
      })
      .addCase(fetchRecalls.fulfilled, (state, action) => {
        state.status = "succeeded";
        state.items = action.payload;
      })
      .addCase(fetchRecalls.rejected, (state, action) => {
        state.status = "failed";
        state.error = action.payload;
      })
      .addCase(createRecall.fulfilled, (state, action) => {
        state.items.push(action.payload);
        state.error = null;
      })
      .addCase(createRecall.rejected, (state, action) => {
        state.error = action.payload;
      })
      .addCase(updateRecall.fulfilled, (state, action) => {
        const i = state.items.findIndex((r) => r.id === action.payload.id);
        if (i !== -1) state.items[i] = action.payload;
        state.error = null;
      })
      .addCase(updateRecall.rejected, (state, action) => {
        state.error = action.payload;
      })
      .addCase(deleteRecall.fulfilled, (state, action) => {
        state.items = state.items.filter((r) => r.id !== action.payload);
        state.error = null;
      })
      .addCase(deleteRecall.rejected, (state, action) => {
        state.error = action.payload;
      });
  },
});

export const { clearRecallError } = recallsSlice.actions;
export default recallsSlice.reducer;
