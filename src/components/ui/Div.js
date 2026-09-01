import React from "react";

export const Div = () => {
  return (
    <div className="absolute w-[280px] h-[150px] top-[320px] left-[50px] bg-white border border-gray-200 rounded-md">
      {/* Bottom left panel */}
      <div className="p-4">
        <h3 className="text-black font-medium mb-3">System Status</h3>
        <div className="space-y-2">
          <div className="flex justify-between items-center">
            <span className="text-black text-sm">Recording:</span>
            <span className="text-green-600 text-sm font-medium">Active</span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-black text-sm">Storage:</span>
            <span className="text-blue-600 text-sm font-medium">85% Used</span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-black text-sm">Network:</span>
            <span className="text-green-600 text-sm font-medium">Connected</span>
          </div>
        </div>
      </div>
    </div>
  );
};
