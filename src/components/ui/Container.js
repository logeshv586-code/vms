import React from "react";

export const Container = () => {
  return (
    <div className="absolute w-[1240px] h-[70px] top-0 left-0 bg-white border-b border-gray-200">
      {/* Header container with white background */}
      <div className="flex items-center justify-between h-full px-6">
        <div className="text-black font-semibold text-lg">
          VMS Dashboard
        </div>
        <div className="flex items-center space-x-4">
          <button className="px-4 py-2 bg-black text-white rounded-md hover:bg-gray-800 transition-colors">
            Settings
          </button>
        </div>
      </div>
    </div>
  );
};
